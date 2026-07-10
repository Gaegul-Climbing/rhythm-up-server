import datetime
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.core.time import load_timezone
from app.domains.accounts.models import User
from app.domains.branches.models import Branch, BranchStatus, Room, RoomStatus, RoomType
from app.domains.reservations.hold_service import create_hold as create_hold_service
from app.domains.reservations.models import Reservation, ReservationSlot, ReservationStatus
from app.domains.reservations.service import cancel_reservation

SEOUL = load_timezone("Asia/Seoul")


@dataclass(frozen=True)
class ReservationTestData:
    branch_id: UUID
    room_id: UUID
    second_room_id: UUID
    start_at: datetime.datetime


@pytest_asyncio.fixture
async def reservation_data(db_session: AsyncSession) -> ReservationTestData:
    branch = Branch(
        id=uuid4(),
        name="리듬업 연습실 테스트점",
        slug=f"test-{uuid4()}",
        address="서울특별시 테스트구 테스트로 1",
        phone="02-1234-5678",
        opens_at=datetime.time(9),
        closes_at=datetime.time(0),
        status=BranchStatus.OPEN,
    )
    room = Room(
        id=uuid4(),
        branch=branch,
        name="보컬 A",
        room_type=RoomType.VOCAL,
        recommended_capacity=1,
        max_capacity=2,
        hourly_rate=15000,
        status=RoomStatus.AVAILABLE,
    )
    second_room = Room(
        id=uuid4(),
        branch=branch,
        name="보컬 B",
        room_type=RoomType.VOCAL,
        recommended_capacity=1,
        max_capacity=2,
        hourly_rate=15000,
        status=RoomStatus.AVAILABLE,
    )
    db_session.add_all([branch, room, second_room])
    await db_session.commit()

    target_date = datetime.datetime.now(SEOUL).date() + datetime.timedelta(days=2)
    return ReservationTestData(
        branch_id=branch.id,
        room_id=room.id,
        second_room_id=second_room.id,
        start_at=datetime.datetime.combine(target_date, datetime.time(10), SEOUL),
    )


async def create_member(client: AsyncClient, suffix: str = "one") -> dict[str, str]:
    email = f"member-{suffix}@example.com"
    password = "correct-password"
    signup = await client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "name": f"회원 {suffix}",
            "phone": "010-1234-5678",
        },
    )
    assert signup.status_code == 201
    login = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def create_hold(
    client: AsyncClient,
    headers: dict[str, str],
    data: ReservationTestData,
    *,
    room_id: UUID | None = None,
) -> dict:
    response = await client.post(
        "/reservation-holds",
        headers=headers,
        json={
            "branch_id": str(data.branch_id),
            "room_id": str(room_id or data.room_id),
            "start_at": data.start_at.isoformat(),
            "duration_hours": 2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_availability_reflects_hold_and_release(
    client: AsyncClient,
    reservation_data: ReservationTestData,
) -> None:
    headers = await create_member(client)
    date = reservation_data.start_at.date().isoformat()
    path = (
        f"/branches/{reservation_data.branch_id}/rooms/"
        f"{reservation_data.room_id}/availability?date={date}"
    )

    before = await client.get(path)
    expected_start = (
        reservation_data.start_at.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
    )
    target = next(slot for slot in before.json()["slots"] if slot["start_at"] == expected_start)
    assert target["available"] is True

    hold = await create_hold(client, headers, reservation_data)
    during = await client.get(path)
    held_starts = {slot["start_at"] for slot in during.json()["slots"] if not slot["available"]}
    first_utc = reservation_data.start_at.astimezone(datetime.UTC)
    assert first_utc.isoformat().replace("+00:00", "Z") in held_starts

    released = await client.delete(f"/reservation-holds/{hold['id']}", headers=headers)
    assert released.status_code == 204
    after = await client.get(path)
    released_start = first_utc.isoformat().replace("+00:00", "Z")
    released_slot = next(
        slot for slot in after.json()["slots"] if slot["start_at"] == released_start
    )
    assert released_slot["available"] is True


async def test_same_time_can_be_held_by_only_one_user(
    client: AsyncClient,
    reservation_data: ReservationTestData,
) -> None:
    first = await create_member(client, "first")
    second = await create_member(client, "second")
    await create_hold(client, first, reservation_data)

    response = await client.post(
        "/reservation-holds",
        headers=second,
        json={
            "branch_id": str(reservation_data.branch_id),
            "room_id": str(reservation_data.room_id),
            "start_at": reservation_data.start_at.isoformat(),
            "duration_hours": 1,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reservation_time_conflict"


async def test_user_can_have_only_one_active_hold(
    client: AsyncClient,
    reservation_data: ReservationTestData,
) -> None:
    headers = await create_member(client)
    await create_hold(client, headers, reservation_data)

    response = await client.post(
        "/reservation-holds",
        headers=headers,
        json={
            "branch_id": str(reservation_data.branch_id),
            "room_id": str(reservation_data.second_room_id),
            "start_at": (reservation_data.start_at + datetime.timedelta(hours=3)).isoformat(),
            "duration_hours": 1,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "reservation_time_conflict"


async def test_confirm_is_idempotent_and_reservation_can_be_cancelled(
    client: AsyncClient,
    reservation_data: ReservationTestData,
) -> None:
    headers = await create_member(client)
    hold = await create_hold(client, headers, reservation_data)
    confirmation_headers = {**headers, "Idempotency-Key": "confirm-test-0001"}

    first = await client.post(
        "/reservations",
        headers=confirmation_headers,
        json={"hold_id": hold["id"]},
    )
    second = await client.post(
        "/reservations",
        headers=confirmation_headers,
        json={"hold_id": hold["id"]},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    listing = await client.get("/reservations", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    cancelled = await client.delete(
        f"/reservations/{first.json()['id']}",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    second_member = await create_member(client, "after-cancel")
    replacement = await client.post(
        "/reservation-holds",
        headers=second_member,
        json={
            "branch_id": str(reservation_data.branch_id),
            "room_id": str(reservation_data.room_id),
            "start_at": reservation_data.start_at.isoformat(),
            "duration_hours": 2,
        },
    )
    assert replacement.status_code == 201


async def test_user_cannot_hold_another_room_at_reserved_time(
    client: AsyncClient,
    reservation_data: ReservationTestData,
) -> None:
    headers = await create_member(client)
    hold = await create_hold(client, headers, reservation_data)
    confirmed = await client.post(
        "/reservations",
        headers={**headers, "Idempotency-Key": "confirm-test-0002"},
        json={"hold_id": hold["id"]},
    )
    assert confirmed.status_code == 201

    response = await client.post(
        "/reservation-holds",
        headers=headers,
        json={
            "branch_id": str(reservation_data.branch_id),
            "room_id": str(reservation_data.second_room_id),
            "start_at": reservation_data.start_at.isoformat(),
            "duration_hours": 1,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_reservation_time_conflict"


async def test_cancellation_is_rejected_within_24_hours(
    client: AsyncClient,
    db_session: AsyncSession,
    reservation_data: ReservationTestData,
) -> None:
    headers = await create_member(client, "deadline")
    hold = await create_hold(client, headers, reservation_data)
    confirmed = await client.post(
        "/reservations",
        headers={**headers, "Idempotency-Key": "confirm-deadline"},
        json={"hold_id": hold["id"]},
    )
    assert confirmed.status_code == 201
    user = await db_session.scalar(select(User).where(User.email == "member-deadline@example.com"))
    assert user is not None
    reservation_id = UUID(confirmed.json()["id"])
    start_utc = reservation_data.start_at.astimezone(datetime.UTC)

    with pytest.raises(ApplicationError) as captured:
        await cancel_reservation(
            session=db_session,
            user_id=user.id,
            reservation_id=reservation_id,
            now=start_utc - datetime.timedelta(hours=23),
        )

    assert captured.value.code == "reservation_cancellation_deadline_passed"


async def test_database_constraint_prevents_double_booking(
    client: AsyncClient,
    db_session: AsyncSession,
    reservation_data: ReservationTestData,
) -> None:
    first_headers = await create_member(client, "constraint-first")
    hold = await create_hold(client, first_headers, reservation_data)
    confirmed = await client.post(
        "/reservations",
        headers={**first_headers, "Idempotency-Key": "confirm-constraint-first"},
        json={"hold_id": hold["id"]},
    )
    assert confirmed.status_code == 201

    await create_member(client, "constraint-second")
    second_user = await db_session.scalar(
        select(User).where(User.email == "member-constraint-second@example.com")
    )
    assert second_user is not None
    start_utc = reservation_data.start_at.astimezone(datetime.UTC)
    competing = Reservation(
        user_id=second_user.id,
        room_id=reservation_data.room_id,
        start_at=start_utc,
        end_at=start_utc + datetime.timedelta(hours=1),
        status=ReservationStatus.CONFIRMED,
        idempotency_key="competing-reservation",
    )
    competing.slots = [
        ReservationSlot(
            room_id=reservation_data.room_id,
            user_id=second_user.id,
            start_at=start_utc,
        )
    ]
    db_session.add(competing)

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    reservation_count = await db_session.scalar(select(func.count()).select_from(Reservation))
    assert reservation_count == 1


async def test_redis_failure_becomes_service_unavailable_error(
    db_session: AsyncSession,
    reservation_data: ReservationTestData,
) -> None:
    class FailingHoldStore:
        async def acquire(self, *args, **kwargs):
            raise RedisError("redis unavailable")

    with pytest.raises(ApplicationError) as captured:
        await create_hold_service(
            session=db_session,
            store=FailingHoldStore(),
            user_id=uuid4(),
            branch_id=reservation_data.branch_id,
            room_id=reservation_data.room_id,
            start_at=reservation_data.start_at,
            duration_hours=1,
        )

    assert captured.value.status_code == 503
    assert captured.value.code == "reservation_hold_service_unavailable"
