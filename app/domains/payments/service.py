import datetime
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.domains.branches.service import find_bookable_room
from app.domains.payments.models import (
    Payment,
    PaymentEvent,
    PaymentOrder,
    PaymentOrderStatus,
    PaymentStatus,
)
from app.domains.payments.providers.base import (
    PaymentProvider,
    ProviderEvent,
    ProviderPaymentStatus,
)
from app.domains.payments.providers.toss import TossPaymentProviderError
from app.domains.payments.repository import (
    get_event,
    get_order,
    get_order_by_idempotency,
    get_payment_by_provider_id,
    get_payment_for_order,
    get_user_payment,
)
from app.domains.reservations.hold_service import get_user_hold
from app.domains.reservations.holds import HoldStore
from app.domains.reservations.service import confirm_reservation


def payment_error(code: str, message: str, status_code: int) -> ApplicationError:
    return ApplicationError(code=code, message=message, status_code=status_code)


async def create_order(
    *,
    session: AsyncSession,
    store: HoldStore,
    user_id: UUID,
    hold_id: UUID,
    idempotency_key: str,
) -> PaymentOrder:
    existing = await get_order_by_idempotency(session, user_id, idempotency_key)
    if existing:
        return existing
    hold = await get_user_hold(store=store, user_id=user_id, hold_id=hold_id)
    room = await find_bookable_room(session, hold.branch_id, hold.room_id)
    order = PaymentOrder(
        user_id=user_id,
        hold_id=hold.id,
        room_id=room.id,
        start_at=hold.start_at,
        end_at=hold.end_at,
        duration_hours=hold.duration_hours,
        amount=room.hourly_rate * hold.duration_hours,
        status=PaymentOrderStatus.PENDING,
        idempotency_key=idempotency_key,
        expires_at=hold.expires_at,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def find_order(session: AsyncSession, user_id: UUID, order_id: UUID) -> PaymentOrder:
    order = await get_order(session, user_id, order_id)
    if order is None:
        raise payment_error("payment_order_not_found", "결제 주문을 찾을 수 없습니다.", 404)
    return order


async def request_payment(
    *,
    session: AsyncSession,
    store: HoldStore,
    provider: PaymentProvider,
    user_id: UUID,
    order_id: UUID,
    idempotency_key: str,
) -> Payment:
    order = await find_order(session, user_id, order_id)
    existing = await get_payment_for_order(session, order.id)
    if existing:
        return existing
    now = datetime.datetime.now(datetime.UTC)
    expires_at = (
        order.expires_at.replace(tzinfo=datetime.UTC)
        if order.expires_at.tzinfo is None
        else order.expires_at
    )
    if expires_at <= now:
        order.status = PaymentOrderStatus.EXPIRED
        await session.commit()
        raise payment_error("payment_order_expired", "결제 주문이 만료되었습니다.", 409)
    if order.status != PaymentOrderStatus.PENDING:
        raise payment_error("payment_order_not_pending", "결제할 수 없는 주문 상태입니다.", 409)
    await get_user_hold(store=store, user_id=user_id, hold_id=order.hold_id)
    try:
        external = await provider.create_payment(order.id, order.amount)
    except RedisError as error:
        raise payment_error(
            "payment_provider_unavailable", "결제 제공자를 사용할 수 없습니다.", 503
        ) from error
    payment = Payment(
        order_id=order.id,
        provider=provider.name,
        provider_payment_id=external.id,
        amount=order.amount,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    session.add(payment)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        try:
            await provider.cancel_payment(external.id)
        except Exception:
            pass
        raise
    await session.refresh(payment)
    return payment


async def confirm_toss_payment(
    *,
    session: AsyncSession,
    store: HoldStore,
    provider: PaymentProvider,
    user_id: UUID,
    order_id: UUID,
    payment_key: str,
    amount: int,
    idempotency_key: str,
) -> Payment:
    if provider.name != "toss" or not hasattr(provider, "confirm_payment"):
        raise payment_error(
            "payment_provider_not_toss",
            "현재 결제 제공자가 토스페이먼츠로 설정되어 있지 않습니다.",
            409,
        )

    order = await find_order(session, user_id, order_id)
    payment = await get_payment_for_order(session, order.id)
    if payment is None:
        raise payment_error("payment_not_found", "결제 내역을 찾을 수 없습니다.", 404)
    if payment.status == PaymentStatus.APPROVED:
        return payment
    if payment.status != PaymentStatus.PENDING:
        raise payment_error("payment_not_pending", "대기 중인 결제만 승인할 수 있습니다.", 409)
    if amount != order.amount:
        raise payment_error(
            "payment_amount_mismatch",
            "결제 금액이 서버의 주문 금액과 일치하지 않습니다.",
            409,
        )

    try:
        event = await provider.confirm_payment(  # type: ignore[attr-defined]
            payment_key=payment_key,
            order_id=order.id,
            amount=order.amount,
            idempotency_key=idempotency_key,
        )
    except TossPaymentProviderError as error:
        raise payment_error(error.code, error.message, error.status_code) from error

    payment.provider_payment_id = payment_key
    await session.flush()
    return await process_provider_event(
        session=session,
        store=store,
        provider=provider,
        event=event,
    )


async def find_payment(session: AsyncSession, user_id: UUID, payment_id: UUID) -> Payment:
    payment = await get_user_payment(session, user_id, payment_id)
    if payment is None:
        raise payment_error("payment_not_found", "결제 내역을 찾을 수 없습니다.", 404)
    return payment


async def process_provider_event(
    *,
    session: AsyncSession,
    store: HoldStore,
    provider: PaymentProvider,
    event: ProviderEvent,
) -> Payment:
    payment = await get_payment_by_provider_id(session, event.payment_id)
    if payment is None:
        raise payment_error("payment_not_found", "결제 내역을 찾을 수 없습니다.", 404)
    if await get_event(session, event.id):
        return payment
    order = await session.get(PaymentOrder, payment.order_id)
    if order is None or event.order_id != order.id or event.amount != order.amount:
        raise payment_error(
            "invalid_payment_event", "결제 이벤트 정보가 주문과 일치하지 않습니다.", 409
        )
    record = PaymentEvent(
        payment_id=payment.id,
        provider=provider.name,
        provider_event_id=event.id,
        event_type=event.event_type,
        payload=event.as_payload(),
    )
    session.add(record)
    if event.status == ProviderPaymentStatus.FAILED:
        payment.status = PaymentStatus.FAILED
        payment.failure_code = event.failure_code
        order.status = PaymentOrderStatus.FAILED
        await session.commit()
        try:
            hold = await get_user_hold(store=store, user_id=order.user_id, hold_id=order.hold_id)
            await store.release(hold)
        except (ApplicationError, RedisError):
            pass
        await session.refresh(payment)
        return payment
    if event.status != ProviderPaymentStatus.APPROVED:
        raise payment_error("unsupported_payment_event", "처리할 수 없는 결제 이벤트입니다.", 409)
    try:
        await confirm_reservation(
            session=session,
            store=store,
            user_id=order.user_id,
            hold_id=order.hold_id,
            idempotency_key=f"payment-order:{order.id}",
            payment_order_id=order.id,
        )
        payment.status = PaymentStatus.APPROVED
        order.status = PaymentOrderStatus.PAID
        await session.commit()
    except ApplicationError:
        await session.rollback()
        try:
            await provider.cancel_payment(payment.provider_payment_id)
            payment.status = PaymentStatus.REFUNDED
        except Exception:
            payment.status = PaymentStatus.COMPENSATION_PENDING
        payment.failure_code = "reservation_confirmation_failed"
        order.status = PaymentOrderStatus.FAILED
        session.add(record)
        await session.commit()
    await session.refresh(payment)
    return payment


async def reconcile_payment(
    *,
    session: AsyncSession,
    store: HoldStore,
    provider: PaymentProvider,
    user_id: UUID,
    payment_id: UUID,
) -> Payment:
    payment = await find_payment(session, user_id, payment_id)
    external = await provider.get_payment(payment.provider_payment_id)
    if external is None:
        raise payment_error("provider_payment_not_found", "외부 결제 정보를 찾을 수 없습니다.", 502)
    if external.status in (ProviderPaymentStatus.APPROVED, ProviderPaymentStatus.FAILED):
        event = ProviderEvent(
            id=external.terminal_event_id or f"reconcile:{external.id}:{external.status.value}",
            payment_id=external.id,
            order_id=external.order_id,
            amount=external.amount,
            status=external.status,
            failure_code=external.failure_code,
        )
        return await process_provider_event(
            session=session, store=store, provider=provider, event=event
        )
    return payment


async def cancel_payment(
    *,
    session: AsyncSession,
    store: HoldStore,
    provider: PaymentProvider,
    user_id: UUID,
    payment_id: UUID,
) -> Payment:
    payment = await find_payment(session, user_id, payment_id)
    if payment.status != PaymentStatus.PENDING:
        raise payment_error("payment_not_cancellable", "대기 중인 결제만 취소할 수 있습니다.", 409)
    await provider.cancel_payment(payment.provider_payment_id)
    order = await session.get(PaymentOrder, payment.order_id)
    payment.status = PaymentStatus.CANCELLED
    if order:
        order.status = PaymentOrderStatus.CANCELLED
        try:
            hold = await get_user_hold(store=store, user_id=user_id, hold_id=order.hold_id)
            await store.release(hold)
        except (ApplicationError, RedisError):
            pass
    await session.commit()
    await session.refresh(payment)
    return payment
