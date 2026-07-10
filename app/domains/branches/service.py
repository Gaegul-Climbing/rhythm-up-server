from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.domains.branches.models import Branch, BranchStatus, Room, RoomStatus
from app.domains.branches.repository import (
    get_public_branch,
    get_public_room,
    get_room_with_branch,
    list_public_branches,
    list_public_rooms,
)


def branch_not_found_error() -> ApplicationError:
    return ApplicationError(
        code="branch_not_found",
        message="지점을 찾을 수 없습니다.",
        status_code=404,
    )


def room_not_found_error() -> ApplicationError:
    return ApplicationError(
        code="room_not_found",
        message="연습실을 찾을 수 없습니다.",
        status_code=404,
    )


async def find_branches(session: AsyncSession) -> list[Branch]:
    return await list_public_branches(session)


async def find_branch(session: AsyncSession, branch_id: UUID) -> Branch:
    branch = await get_public_branch(session, branch_id)
    if branch is None:
        raise branch_not_found_error()
    return branch


async def find_rooms(session: AsyncSession, branch_id: UUID) -> list[Room]:
    await find_branch(session, branch_id)
    return await list_public_rooms(session, branch_id)


async def find_room(session: AsyncSession, branch_id: UUID, room_id: UUID) -> Room:
    await find_branch(session, branch_id)
    room = await get_public_room(session, branch_id, room_id)
    if room is None:
        raise room_not_found_error()
    return room


async def find_bookable_room(
    session: AsyncSession,
    branch_id: UUID,
    room_id: UUID,
) -> Room:
    room = await get_room_with_branch(session, branch_id, room_id)
    if room is None or room.branch.status == BranchStatus.CLOSED:
        raise room_not_found_error()
    if room.branch.status != BranchStatus.OPEN:
        raise ApplicationError(
            code="branch_unavailable",
            message="현재 예약할 수 없는 지점입니다.",
            status_code=409,
        )
    if room.status == RoomStatus.INACTIVE:
        raise room_not_found_error()
    if room.status != RoomStatus.AVAILABLE:
        raise ApplicationError(
            code="room_unavailable",
            message="현재 예약할 수 없는 연습실입니다.",
            status_code=409,
        )
    return room
