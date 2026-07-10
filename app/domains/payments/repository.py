from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.payments.models import Payment, PaymentEvent, PaymentOrder


async def get_order(session: AsyncSession, user_id: UUID, order_id: UUID) -> PaymentOrder | None:
    return await session.scalar(
        select(PaymentOrder).where(PaymentOrder.id == order_id, PaymentOrder.user_id == user_id)
    )


async def get_order_by_idempotency(
    session: AsyncSession, user_id: UUID, idempotency_key: str
) -> PaymentOrder | None:
    return await session.scalar(
        select(PaymentOrder).where(
            PaymentOrder.user_id == user_id,
            PaymentOrder.idempotency_key == idempotency_key,
        )
    )


async def get_payment_for_order(session: AsyncSession, order_id: UUID) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.order_id == order_id))


async def get_user_payment(
    session: AsyncSession, user_id: UUID, payment_id: UUID
) -> Payment | None:
    return await session.scalar(
        select(Payment)
        .join(PaymentOrder, Payment.order_id == PaymentOrder.id)
        .where(Payment.id == payment_id, PaymentOrder.user_id == user_id)
    )


async def get_payment_by_provider_id(
    session: AsyncSession, provider_payment_id: str
) -> Payment | None:
    return await session.scalar(
        select(Payment).where(Payment.provider_payment_id == provider_payment_id)
    )


async def get_event(session: AsyncSession, provider_event_id: str) -> PaymentEvent | None:
    return await session.scalar(
        select(PaymentEvent).where(PaymentEvent.provider_event_id == provider_event_id)
    )
