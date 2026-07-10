from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.branches.models import Branch, BranchStatus, Room, RoomStatus


async def list_public_branches(session: AsyncSession) -> list[Branch]:
    statement = select(Branch).where(Branch.status != BranchStatus.CLOSED).order_by(Branch.name)
    return list((await session.scalars(statement)).all())


async def get_public_branch(session: AsyncSession, branch_id: UUID) -> Branch | None:
    statement = select(Branch).where(
        Branch.id == branch_id,
        Branch.status != BranchStatus.CLOSED,
    )
    return await session.scalar(statement)


async def list_public_rooms(session: AsyncSession, branch_id: UUID) -> list[Room]:
    statement = (
        select(Room)
        .where(
            Room.branch_id == branch_id,
            Room.status != RoomStatus.INACTIVE,
        )
        .order_by(Room.name)
    )
    return list((await session.scalars(statement)).all())


async def get_public_room(
    session: AsyncSession,
    branch_id: UUID,
    room_id: UUID,
) -> Room | None:
    statement = select(Room).where(
        Room.id == room_id,
        Room.branch_id == branch_id,
        Room.status != RoomStatus.INACTIVE,
    )
    return await session.scalar(statement)


async def get_room_with_branch(
    session: AsyncSession,
    branch_id: UUID,
    room_id: UUID,
) -> Room | None:
    statement = (
        select(Room)
        .options(selectinload(Room.branch))
        .where(Room.id == room_id, Room.branch_id == branch_id)
    )
    return await session.scalar(statement)
