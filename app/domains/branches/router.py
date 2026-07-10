from uuid import UUID

from fastapi import APIRouter

from app.database.dependencies import SessionDependency
from app.domains.branches.schemas import BranchResponse, RoomResponse
from app.domains.branches.service import find_branch, find_branches, find_room, find_rooms

router = APIRouter(prefix="/branches")


@router.get("", response_model=list[BranchResponse])
async def get_branches(session: SessionDependency) -> list[BranchResponse]:
    branches = await find_branches(session)
    return [BranchResponse.model_validate(branch) for branch in branches]


@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(branch_id: UUID, session: SessionDependency) -> BranchResponse:
    branch = await find_branch(session, branch_id)
    return BranchResponse.model_validate(branch)


@router.get("/{branch_id}/rooms", response_model=list[RoomResponse])
async def get_rooms(branch_id: UUID, session: SessionDependency) -> list[RoomResponse]:
    rooms = await find_rooms(session, branch_id)
    return [RoomResponse.model_validate(room) for room in rooms]


@router.get("/{branch_id}/rooms/{room_id}", response_model=RoomResponse)
async def get_room(
    branch_id: UUID,
    room_id: UUID,
    session: SessionDependency,
) -> RoomResponse:
    room = await find_room(session, branch_id, room_id)
    return RoomResponse.model_validate(room)
