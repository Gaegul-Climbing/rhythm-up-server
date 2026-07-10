import datetime
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.time import load_timezone
from app.domains.branches.service import find_bookable_room
from app.domains.reservations.holds import HoldStore
from app.domains.reservations.repository import list_room_slot_starts
from app.domains.reservations.rules import (
    ReservationRuleError,
    daily_slots,
)
from app.domains.reservations.schemas import AvailabilityResponse, AvailabilitySlotResponse


def rule_error(error: ReservationRuleError) -> ApplicationError:
    return ApplicationError(code=error.code, message=error.message, status_code=422)


def hold_service_unavailable_error() -> ApplicationError:
    return ApplicationError(
        code="reservation_hold_service_unavailable",
        message="임시 선점 서비스를 사용할 수 없습니다.",
        status_code=503,
    )


async def get_availability(
    *,
    session: AsyncSession,
    store: HoldStore,
    branch_id: UUID,
    room_id: UUID,
    target_date: datetime.date,
    now: datetime.datetime | None = None,
) -> AvailabilityResponse:
    settings = get_settings()
    timezone = load_timezone(settings.business_timezone)
    room = await find_bookable_room(session, branch_id, room_id)
    utc_now = now or datetime.datetime.now(datetime.UTC)

    try:
        slots = daily_slots(
            target_date=target_date,
            opens_at=room.branch.opens_at,
            closes_at=room.branch.closes_at,
            timezone=timezone,
            now=utc_now,
        )
    except ReservationRuleError as error:
        raise rule_error(error) from error

    if not slots:
        return AvailabilityResponse(
            room_id=room.id,
            date=target_date,
            timezone=settings.business_timezone,
            slots=[],
        )

    reserved = await list_room_slot_starts(
        session,
        room.id,
        slots[0],
        slots[-1] + datetime.timedelta(hours=1),
    )
    try:
        held = await store.busy_slots(room.id, slots)
    except RedisError as error:
        raise hold_service_unavailable_error() from error

    earliest_start = utc_now.astimezone(datetime.UTC) + datetime.timedelta(hours=1)
    responses = [
        AvailabilitySlotResponse(
            start_at=slot,
            end_at=slot + datetime.timedelta(hours=1),
            available=slot >= earliest_start and slot not in reserved and slot not in held,
        )
        for slot in slots
    ]
    return AvailabilityResponse(
        room_id=room.id,
        date=target_date,
        timezone=settings.business_timezone,
        slots=responses,
    )
