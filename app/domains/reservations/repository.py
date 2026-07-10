import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.reservations.models import Reservation, ReservationSlot


def normalize_db_datetime(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.UTC)
    return value.astimezone(datetime.UTC)


async def list_room_slot_starts(
    session: AsyncSession,
    room_id: UUID,
    starts_at: datetime.datetime,
    ends_at: datetime.datetime,
) -> set[datetime.datetime]:
    statement = select(ReservationSlot.start_at).where(
        ReservationSlot.room_id == room_id,
        ReservationSlot.start_at >= starts_at,
        ReservationSlot.start_at < ends_at,
    )
    values = (await session.scalars(statement)).all()
    return {normalize_db_datetime(value) for value in values}


async def has_room_slot_conflict(
    session: AsyncSession,
    room_id: UUID,
    slot_starts: tuple[datetime.datetime, ...],
) -> bool:
    statement = (
        select(ReservationSlot.id)
        .where(
            ReservationSlot.room_id == room_id,
            ReservationSlot.start_at.in_(slot_starts),
        )
        .limit(1)
    )
    return await session.scalar(statement) is not None


async def has_user_slot_conflict(
    session: AsyncSession,
    user_id: UUID,
    slot_starts: tuple[datetime.datetime, ...],
) -> bool:
    statement = (
        select(ReservationSlot.id)
        .where(
            ReservationSlot.user_id == user_id,
            ReservationSlot.start_at.in_(slot_starts),
        )
        .limit(1)
    )
    return await session.scalar(statement) is not None


async def get_reservation_by_idempotency_key(
    session: AsyncSession,
    user_id: UUID,
    idempotency_key: str,
) -> Reservation | None:
    statement = select(Reservation).where(
        Reservation.user_id == user_id,
        Reservation.idempotency_key == idempotency_key,
    )
    return await session.scalar(statement)


async def list_user_reservations(
    session: AsyncSession,
    user_id: UUID,
) -> list[Reservation]:
    statement = (
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.start_at.desc())
    )
    return list((await session.scalars(statement)).all())


async def get_user_reservation(
    session: AsyncSession,
    user_id: UUID,
    reservation_id: UUID,
) -> Reservation | None:
    statement = select(Reservation).where(
        Reservation.id == reservation_id,
        Reservation.user_id == user_id,
    )
    return await session.scalar(statement)


async def delete_reservation_slots(
    session: AsyncSession,
    reservation_id: UUID,
) -> None:
    await session.execute(
        delete(ReservationSlot).where(ReservationSlot.reservation_id == reservation_id)
    )
