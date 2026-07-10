import datetime
from uuid import UUID, uuid4

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.time import load_timezone
from app.domains.branches.service import find_bookable_room
from app.domains.reservations.availability import (
    hold_service_unavailable_error,
    rule_error,
)
from app.domains.reservations.holds import HoldStore, ReservationHold
from app.domains.reservations.repository import (
    has_room_slot_conflict,
    has_user_slot_conflict,
)
from app.domains.reservations.rules import ReservationRuleError, build_period


def hold_not_found_error() -> ApplicationError:
    return ApplicationError(
        code="reservation_hold_not_found",
        message="임시 선점을 찾을 수 없거나 이미 만료되었습니다.",
        status_code=404,
    )


def reservation_conflict_error() -> ApplicationError:
    return ApplicationError(
        code="reservation_time_conflict",
        message="선택한 시간 중 이미 예약되었거나 선점된 시간이 있습니다.",
        status_code=409,
    )


async def create_hold(
    *,
    session: AsyncSession,
    store: HoldStore,
    user_id: UUID,
    branch_id: UUID,
    room_id: UUID,
    start_at: datetime.datetime,
    duration_hours: int,
    now: datetime.datetime | None = None,
) -> ReservationHold:
    settings = get_settings()
    timezone = load_timezone(settings.business_timezone)
    utc_now = now or datetime.datetime.now(datetime.UTC)
    room = await find_bookable_room(session, branch_id, room_id)

    try:
        period = build_period(
            start_at=start_at,
            duration_hours=duration_hours,
            opens_at=room.branch.opens_at,
            closes_at=room.branch.closes_at,
            timezone=timezone,
            now=utc_now,
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

    hold = ReservationHold(
        id=uuid4(),
        user_id=user_id,
        branch_id=branch_id,
        room_id=room.id,
        start_at=period.start_at,
        end_at=period.end_at,
        duration_hours=duration_hours,
        expires_at=utc_now.astimezone(datetime.UTC)
        + datetime.timedelta(seconds=settings.reservation_hold_ttl_seconds),
        slot_starts=period.slot_starts,
    )
    try:
        acquired = await store.acquire(hold, settings.reservation_hold_ttl_seconds)
    except RedisError as error:
        raise hold_service_unavailable_error() from error
    if not acquired:
        raise reservation_conflict_error()
    return hold


async def get_user_hold(
    *,
    store: HoldStore,
    user_id: UUID,
    hold_id: UUID,
) -> ReservationHold:
    try:
        hold = await store.get(hold_id)
    except RedisError as error:
        raise hold_service_unavailable_error() from error
    if hold is None or hold.user_id != user_id:
        raise hold_not_found_error()
    return hold


async def release_user_hold(
    *,
    store: HoldStore,
    user_id: UUID,
    hold_id: UUID,
) -> None:
    hold = await get_user_hold(store=store, user_id=user_id, hold_id=hold_id)
    try:
        await store.release(hold)
    except RedisError as error:
        raise hold_service_unavailable_error() from error
