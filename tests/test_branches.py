import datetime
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.branches.models import (
    Branch,
    BranchStatus,
    Room,
    RoomStatus,
    RoomType,
)


@dataclass(frozen=True)
class BranchTestData:
    open_branch_id: UUID
    closed_branch_id: UUID
    temporarily_closed_branch_id: UUID
    available_room_id: UUID
    maintenance_room_id: UUID
    inactive_room_id: UUID


@pytest_asyncio.fixture
async def branch_data(db_session: AsyncSession) -> BranchTestData:
    open_branch = Branch(
        id=uuid4(),
        name="리듬업 연습실 강남점",
        slug="gangnam",
        address="서울특별시 강남구 테헤란로 100",
        phone="02-1000-1001",
        opens_at=datetime.time(9, 0),
        closes_at=datetime.time(0, 0),
        status=BranchStatus.OPEN,
    )
    closed_branch = Branch(
        id=uuid4(),
        name="리듬업 연습실 폐점",
        slug="closed",
        address="서울특별시 중구 폐점로 1",
        phone="02-1000-1002",
        opens_at=datetime.time(9, 0),
        closes_at=datetime.time(0, 0),
        status=BranchStatus.CLOSED,
    )
    temporarily_closed_branch = Branch(
        id=uuid4(),
        name="리듬업 연습실 성수점",
        slug="seongsu",
        address="서울특별시 성동구 연무장길 100",
        phone="02-1000-1003",
        opens_at=datetime.time(9, 0),
        closes_at=datetime.time(0, 0),
        status=BranchStatus.TEMPORARILY_CLOSED,
    )
    available_room = Room(
        id=uuid4(),
        branch=open_branch,
        name="보컬 A",
        room_type=RoomType.VOCAL,
        recommended_capacity=1,
        max_capacity=2,
        hourly_rate=15000,
        status=RoomStatus.AVAILABLE,
    )
    maintenance_room = Room(
        id=uuid4(),
        branch=open_branch,
        name="댄스 A",
        room_type=RoomType.DANCE,
        recommended_capacity=4,
        max_capacity=8,
        hourly_rate=25000,
        status=RoomStatus.MAINTENANCE,
    )
    inactive_room = Room(
        id=uuid4(),
        branch=open_branch,
        name="사용 중단 룸",
        room_type=RoomType.BAND,
        recommended_capacity=4,
        max_capacity=6,
        hourly_rate=30000,
        status=RoomStatus.INACTIVE,
    )
    db_session.add_all(
        [
            open_branch,
            closed_branch,
            temporarily_closed_branch,
            available_room,
            maintenance_room,
            inactive_room,
        ]
    )
    await db_session.commit()

    return BranchTestData(
        open_branch_id=open_branch.id,
        closed_branch_id=closed_branch.id,
        temporarily_closed_branch_id=temporarily_closed_branch.id,
        available_room_id=available_room.id,
        maintenance_room_id=maintenance_room.id,
        inactive_room_id=inactive_room.id,
    )


async def test_list_branches_hides_permanently_closed_branch(
    client: AsyncClient,
    branch_data: BranchTestData,
) -> None:
    response = await client.get("/branches")

    assert response.status_code == 200
    branch_ids = {item["id"] for item in response.json()}
    assert str(branch_data.open_branch_id) in branch_ids
    assert str(branch_data.temporarily_closed_branch_id) in branch_ids
    assert str(branch_data.closed_branch_id) not in branch_ids


async def test_get_temporarily_closed_branch_exposes_status(
    client: AsyncClient,
    branch_data: BranchTestData,
) -> None:
    response = await client.get(f"/branches/{branch_data.temporarily_closed_branch_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "temporarily_closed"


async def test_get_closed_branch_returns_not_found(
    client: AsyncClient,
    branch_data: BranchTestData,
) -> None:
    response = await client.get(f"/branches/{branch_data.closed_branch_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "branch_not_found"


async def test_list_rooms_hides_inactive_room_and_exposes_maintenance(
    client: AsyncClient,
    branch_data: BranchTestData,
) -> None:
    response = await client.get(f"/branches/{branch_data.open_branch_id}/rooms")

    assert response.status_code == 200
    rooms = {item["id"]: item for item in response.json()}
    assert str(branch_data.available_room_id) in rooms
    assert rooms[str(branch_data.maintenance_room_id)]["status"] == "maintenance"
    assert str(branch_data.inactive_room_id) not in rooms


async def test_get_room_rejects_inactive_room(
    client: AsyncClient,
    branch_data: BranchTestData,
) -> None:
    response = await client.get(
        f"/branches/{branch_data.open_branch_id}/rooms/{branch_data.inactive_room_id}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "room_not_found"
