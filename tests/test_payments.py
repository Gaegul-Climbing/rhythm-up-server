import datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import load_timezone
from app.domains.branches.models import Branch, BranchStatus, Room, RoomStatus, RoomType
from app.domains.payments.models import PaymentEvent
from app.domains.reservations.models import Reservation

SEOUL = load_timezone("Asia/Seoul")


async def setup_member_room(client: AsyncClient, db: AsyncSession, suffix: str = "pay"):
    email = f"{suffix}-{uuid4().hex}@example.com"
    password = "correct-password"
    await client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "name": "결제 테스트",
            "phone": "010-1234-5678",
        },
    )
    login = await client.post("/auth/login", data={"username": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    branch = Branch(
        name="리듬업 테스트점",
        slug=f"pay-{uuid4().hex}",
        address="서울시 테스트로 1",
        phone="02-1234-5678",
        opens_at=datetime.time(9),
        closes_at=datetime.time(0),
        status=BranchStatus.OPEN,
    )
    room = Room(
        branch=branch,
        name="보컬 A",
        room_type=RoomType.VOCAL,
        recommended_capacity=1,
        max_capacity=2,
        hourly_rate=15000,
        status=RoomStatus.AVAILABLE,
    )
    db.add_all([branch, room])
    await db.commit()
    start = datetime.datetime.combine(
        datetime.datetime.now(SEOUL).date() + datetime.timedelta(days=2),
        datetime.time(10),
        SEOUL,
    )
    hold = await client.post(
        "/reservation-holds",
        headers=headers,
        json={
            "branch_id": str(branch.id),
            "room_id": str(room.id),
            "start_at": start.isoformat(),
            "duration_hours": 2,
        },
    )
    assert hold.status_code == 201, hold.text
    return headers, hold.json()


async def create_order_and_payment(client: AsyncClient, db: AsyncSession):
    headers, hold = await setup_member_room(client, db)
    order = await client.post(
        "/payment-orders",
        headers={**headers, "Idempotency-Key": "order-key-001"},
        json={"hold_id": hold["id"]},
    )
    assert order.status_code == 201, order.text
    assert order.json()["amount"] == 30000
    payment = await client.post(
        "/payments",
        headers={**headers, "Idempotency-Key": "payment-key-001"},
        json={"order_id": order.json()["id"]},
    )
    assert payment.status_code == 201, payment.text
    return headers, hold, order.json(), payment.json()


@pytest.mark.asyncio
async def test_payment_approval_confirms_reservation_idempotently(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers, _, order, payment = await create_order_and_payment(client, db_session)
    complete = await client.post(
        f"/mock-payment-provider/payments/{payment['id']}/complete",
        headers=headers,
        json={"outcome": "approved", "deliver_event": True},
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["payment"]["status"] == "approved"
    repeated = await client.post(
        f"/mock-payment-provider/payments/{payment['id']}/complete",
        headers=headers,
        json={"outcome": "approved", "deliver_event": True},
    )
    assert repeated.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Reservation)) == 1
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
    fetched = await client.get(f"/payment-orders/{order['id']}", headers=headers)
    assert fetched.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_lost_event_is_recovered_by_reconciliation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers, _, _, payment = await create_order_and_payment(client, db_session)
    complete = await client.post(
        f"/mock-payment-provider/payments/{payment['id']}/complete",
        headers=headers,
        json={"outcome": "approved", "deliver_event": False},
    )
    assert complete.json()["payment"]["status"] == "pending"
    reconciled = await client.post(f"/payments/{payment['id']}/reconcile", headers=headers)
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_failed_payment_releases_hold(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers, hold, _, payment = await create_order_and_payment(client, db_session)
    failed = await client.post(
        f"/mock-payment-provider/payments/{payment['id']}/complete",
        headers=headers,
        json={"outcome": "failed", "deliver_event": True},
    )
    assert failed.status_code == 200
    assert failed.json()["payment"]["status"] == "failed"
    missing = await client.get(f"/reservation-holds/{hold['id']}", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_pending_payment_can_be_cancelled(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers, _, _, payment = await create_order_and_payment(client, db_session)
    cancelled = await client.delete(f"/payments/{payment['id']}", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_mock_completion_is_disabled_when_toss_is_active(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as context:
        context.setenv("PAYMENT_PROVIDER", "toss")
        get_settings.cache_clear()
        headers, _, _, payment = await create_order_and_payment(client, db_session)

        response = await client.post(
            f"/mock-payment-provider/payments/{payment['id']}/complete",
            headers=headers,
            json={"outcome": "approved", "deliver_event": True},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "mock_payment_provider_disabled"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_toss_checkout_urls_use_configured_public_urls(
    client: AsyncClient,
    db_session: AsyncSession,
    payment_provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as context:
        context.setenv("TOSS_PAYMENTS_SUCCESS_URL", "https://rhythm-up.example/success")
        context.setenv("TOSS_PAYMENTS_FAIL_URL", "https://rhythm-up.example/fail")
        get_settings.cache_clear()
        payment_provider.name = "toss"
        headers, hold = await setup_member_room(client, db_session, suffix="toss-url")
        order = await client.post(
            "/payment-orders",
            headers={**headers, "Idempotency-Key": "toss-url-order"},
            json={"hold_id": hold["id"]},
        )
        payment = await client.post(
            "/payments",
            headers={
                **headers,
                "Idempotency-Key": "toss-url-payment",
                "Host": "127.0.0.1:8000",
            },
            json={"order_id": order.json()["id"]},
        )

        assert payment.status_code == 201, payment.text
        checkout = payment.json()["checkout"]
        assert checkout["success_url"] == "https://rhythm-up.example/success"
        assert checkout["fail_url"] == "https://rhythm-up.example/fail"
    get_settings.cache_clear()
