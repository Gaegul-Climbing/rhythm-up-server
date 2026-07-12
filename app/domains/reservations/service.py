import datetime
import logging
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.time import load_timezone
from app.domains.branches.service import find_bookable_room
from app.domains.payments.models import (
    PaymentEvent,
    PaymentOrder,
    PaymentOrderStatus,
    PaymentStatus,
)
from app.domains.payments.providers.base import PaymentProvider, ProviderPaymentStatus
from app.domains.payments.providers.toss import TossPaymentProviderError
from app.domains.payments.repository import get_payment_for_order
from app.domains.reservations.availability import rule_error
from app.domains.reservations.hold_service import (
    get_user_hold,
    reservation_conflict_error,
)
from app.domains.reservations.holds import HoldStore
from app.domains.reservations.models import (
    Reservation,
    ReservationSlot,
    ReservationStatus,
)
from app.domains.reservations.repository import (
    delete_reservation_slots,
    get_reservation_by_idempotency_key,
    get_user_reservation,
    has_room_slot_conflict,
    has_user_slot_conflict,
    list_user_reservations,
    normalize_db_datetime,
)
from app.domains.reservations.rules import ReservationRuleError, build_period

logger = logging.getLogger(__name__)


def reservation_not_found_error() -> ApplicationError:
    return ApplicationError(
        code="reservation_not_found",
        message="예약을 찾을 수 없습니다.",
        status_code=404,
    )


async def confirm_reservation(
    *,
    session: AsyncSession,
    store: HoldStore,
    user_id: UUID,
    hold_id: UUID,
    idempotency_key: str,
    payment_order_id: UUID,
    now: datetime.datetime | None = None,
) -> Reservation:
    existing = await get_reservation_by_idempotency_key(session, user_id, idempotency_key)
    if existing is not None:
        return existing

    hold = await get_user_hold(store=store, user_id=user_id, hold_id=hold_id)
    room = await find_bookable_room(session, hold.branch_id, hold.room_id)
    settings = get_settings()
    try:
        period = build_period(
            start_at=hold.start_at,
            duration_hours=hold.duration_hours,
            opens_at=room.branch.opens_at,
            closes_at=room.branch.closes_at,
            timezone=load_timezone(settings.business_timezone),
            now=now,
        )
    except ReservationRuleError as error:
        raise rule_error(error) from error

    if await has_room_slot_conflict(session, room.id, period.slot_starts):
        raise reservation_conflict_error()
    if await has_user_slot_conflict(session, user_id, period.slot_starts):
        raise ApplicationError(
            code="user_reservation_time_conflict",
            message="같은 시간에 다른 예약이 있습니다.",
            status_code=409,
        )

    reservation = Reservation(
        user_id=user_id,
        room_id=room.id,
        start_at=period.start_at,
        end_at=period.end_at,
        status=ReservationStatus.CONFIRMED,
        idempotency_key=idempotency_key,
        payment_order_id=payment_order_id,
    )
    reservation.slots = [
        ReservationSlot(room_id=room.id, user_id=user_id, start_at=slot)
        for slot in period.slot_starts
    ]
    session.add(reservation)

    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        existing = await get_reservation_by_idempotency_key(
            session,
            user_id,
            idempotency_key,
        )
        if existing is not None:
            return existing
        raise reservation_conflict_error() from error

    await session.refresh(reservation)
    try:
        await store.release(hold)
    except RedisError:
        logger.exception("Failed to release confirmed reservation hold", extra={"hold_id": hold.id})
    return reservation


async def find_user_reservations(
    session: AsyncSession,
    user_id: UUID,
) -> list[Reservation]:
    return await list_user_reservations(session, user_id)


async def find_user_reservation(
    session: AsyncSession,
    user_id: UUID,
    reservation_id: UUID,
) -> Reservation:
    reservation = await get_user_reservation(session, user_id, reservation_id)
    if reservation is None:
        raise reservation_not_found_error()
    return reservation


async def cancel_reservation(
    *,
    session: AsyncSession,
    provider: PaymentProvider,
    user_id: UUID,
    reservation_id: UUID,
    now: datetime.datetime | None = None,
) -> Reservation:
    reservation = await find_user_reservation(session, user_id, reservation_id)
    if reservation.status != ReservationStatus.CONFIRMED:
        raise ApplicationError(
            code="reservation_already_cancelled",
            message="이미 취소된 예약입니다.",
            status_code=409,
        )

    utc_now = (now or datetime.datetime.now(datetime.UTC)).astimezone(datetime.UTC)
    start_at = normalize_db_datetime(reservation.start_at)
    if utc_now > start_at - datetime.timedelta(hours=24):
        raise ApplicationError(
            code="reservation_cancellation_deadline_passed",
            message="이용 시작 24시간 전까지만 예약을 취소할 수 있습니다.",
            status_code=409,
        )

    await refund_reservation_payment(session=session, provider=provider, reservation=reservation)
    await delete_reservation_slots(session, reservation.id)
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = utc_now
    try:
        await session.commit()
    except Exception as error:
        await session.rollback()
        logger.exception(
            "Reservation cancellation state was not persisted after provider refund",
            extra={"reservation_id": reservation.id},
        )
        raise ApplicationError(
            code="reservation_cancellation_reconciliation_required",
            message="결제 취소 후 예약 상태를 저장하지 못했습니다. 관리자 확인이 필요합니다.",
            status_code=503,
        ) from error
    await session.refresh(reservation)
    return reservation


async def refund_reservation_payment(
    *,
    session: AsyncSession,
    provider: PaymentProvider,
    reservation: Reservation,
) -> None:
    if reservation.payment_order_id is None:
        return

    payment = await get_payment_for_order(session, reservation.payment_order_id)
    order = await session.get(PaymentOrder, reservation.payment_order_id)
    if payment is None or order is None:
        raise ApplicationError(
            code="reservation_payment_not_found",
            message="예약에 연결된 결제 정보를 찾을 수 없습니다.",
            status_code=409,
        )
    if payment.status == PaymentStatus.REFUNDED:
        return
    if payment.status != PaymentStatus.APPROVED:
        raise ApplicationError(
            code="reservation_payment_not_refundable",
            message="승인된 결제만 예약 취소와 함께 환불할 수 있습니다.",
            status_code=409,
        )

    try:
        refunded = await provider.cancel_payment(payment.provider_payment_id)
    except TossPaymentProviderError as error:
        raise ApplicationError(
            code=error.code,
            message=error.message,
            status_code=error.status_code,
        ) from error
    except Exception as error:
        logger.exception(
            "Reservation payment refund failed",
            extra={"reservation_id": reservation.id, "payment_id": payment.id},
        )
        raise ApplicationError(
            code="reservation_payment_refund_failed",
            message="결제 취소에 실패해 예약을 취소할 수 없습니다.",
            status_code=502,
        ) from error

    if refunded.status != ProviderPaymentStatus.CANCELLED:
        raise ApplicationError(
            code="reservation_payment_refund_incomplete",
            message="결제 취소가 완료되지 않아 예약을 취소할 수 없습니다.",
            status_code=502,
        )

    payment.status = PaymentStatus.REFUNDED
    payment.failure_code = None
    order.status = PaymentOrderStatus.CANCELLED
    session.add(
        PaymentEvent(
            payment_id=payment.id,
            provider=provider.name,
            provider_event_id=f"reservation-refund:{reservation.id}",
            event_type="payment.refunded",
            payload={
                "reservation_id": str(reservation.id),
                "payment_id": refunded.id,
                "order_id": str(refunded.order_id),
                "amount": refunded.amount,
                "status": refunded.status.value,
            },
        )
    )
