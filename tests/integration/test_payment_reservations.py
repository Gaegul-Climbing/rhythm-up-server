import datetime
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.time import load_timezone
from app.domains.accounts.models import User
from app.domains.branches.models import Branch, BranchStatus, Room, RoomStatus, RoomType
from app.domains.payments.models import Payment, PaymentOrder, PaymentOrderStatus, PaymentStatus
from app.domains.payments.providers.base import ProviderPaymentStatus
from app.domains.payments.providers.local import LocalPaymentProvider
from app.domains.payments.service import create_order, process_provider_event, request_payment
from app.domains.reservations.hold_service import create_hold
from app.domains.reservations.holds import RedisHoldStore
from app.domains.reservations.models import Reservation

pytestmark = pytest.mark.integration


def get_test_settings() -> Settings:
    settings = Settings(_env_file=".env.test")
    if settings.app_env != "test":
        raise RuntimeError("통합 테스트는 APP_ENV=test인 .env.test 또는 환경변수가 필요합니다.")
    return settings


@dataclass(frozen=True)
class IntegrationRoom:
    branch_id: UUID
    room_id: UUID
    start_at: datetime.datetime


async def create_room(session: AsyncSession) -> IntegrationRoom:
    branch = Branch(
        id=uuid4(),
        name=f"통합 테스트점 {uuid4().hex[:8]}",
        slug=f"integration-{uuid4().hex}",
        address="서울시 테스트구 테스트로 1",
        phone="02-1234-5678",
        opens_at=datetime.time(9),
        closes_at=datetime.time(0),
        status=BranchStatus.OPEN,
    )
    room = Room(
        id=uuid4(),
        branch=branch,
        name="통합 보컬 A",
        room_type=RoomType.VOCAL,
        recommended_capacity=1,
        max_capacity=2,
        hourly_rate=15000,
        status=RoomStatus.AVAILABLE,
    )
    session.add_all([branch, room])
    await session.commit()

    seoul = load_timezone("Asia/Seoul")
    start_at = datetime.datetime.combine(
        datetime.datetime.now(seoul).date() + datetime.timedelta(days=2),
        datetime.time(10),
        seoul,
    )
    return IntegrationRoom(branch_id=branch.id, room_id=room.id, start_at=start_at)


async def create_user(session: AsyncSession, *, suffix: str) -> User:
    user = User(
        id=uuid4(),
        email=f"integration-{suffix}-{uuid4().hex}@example.com",
        password_hash="not-used-in-integration-test",
        name="통합 테스트 사용자",
        phone="010-1234-5678",
    )
    session.add(user)
    await session.commit()
    return user


async def create_pending_payment_for_hold(
    *,
    session: AsyncSession,
    store: RedisHoldStore,
    provider: LocalPaymentProvider,
    user_id: UUID,
    room: IntegrationRoom,
    key_suffix: str,
):
    hold = await create_hold(
        session=session,
        store=store,
        user_id=user_id,
        branch_id=room.branch_id,
        room_id=room.room_id,
        start_at=room.start_at,
        duration_hours=2,
    )
    order = await create_order(
        session=session,
        store=store,
        user_id=user_id,
        hold_id=hold.id,
        idempotency_key=f"integration-order-{key_suffix}",
    )
    payment = await request_payment(
        session=session,
        store=store,
        provider=provider,
        user_id=user_id,
        order_id=order.id,
        idempotency_key=f"integration-payment-{key_suffix}",
    )
    return payment


async def approve_payment(
    *,
    session: AsyncSession,
    store: RedisHoldStore,
    provider: LocalPaymentProvider,
    payment: Payment,
):
    event = await provider.complete_payment(
        payment.provider_payment_id,
        ProviderPaymentStatus.APPROVED,
    )
    return await process_provider_event(
        session=session,
        store=store,
        provider=provider,
        event=event,
    )


async def test_paid_reservation_is_confirmed_with_postgresql_and_redis() -> None:
    settings = get_test_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    store = RedisHoldStore(redis, prefix=f"integration-payment-{uuid4()}")
    provider = LocalPaymentProvider(
        redis,
        prefix=f"integration-provider-{uuid4()}",
        ttl_seconds=settings.local_payment_state_ttl_seconds,
    )

    try:
        async with session_factory() as session:
            room = await create_room(session)
            user = await create_user(session, suffix="paid")
            payment = await create_pending_payment_for_hold(
                session=session,
                store=store,
                provider=provider,
                user_id=user.id,
                room=room,
                key_suffix="paid",
            )
            payment = await approve_payment(
                session=session,
                store=store,
                provider=provider,
                payment=payment,
            )

            reservation_count = await session.scalar(
                select(func.count()).select_from(Reservation).where(Reservation.user_id == user.id)
            )
            assert payment.status == PaymentStatus.APPROVED
            assert reservation_count == 1
    finally:
        await redis.aclose()
        await engine.dispose()


async def test_second_payment_for_same_slot_is_refunded_without_second_reservation() -> None:
    settings = get_test_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    provider = LocalPaymentProvider(
        redis,
        prefix=f"integration-provider-{uuid4()}",
        ttl_seconds=settings.local_payment_state_ttl_seconds,
    )

    try:
        async with session_factory() as session:
            room = await create_room(session)
            first_user = await create_user(session, suffix="first")
            second_user = await create_user(session, suffix="second")
            first_store = RedisHoldStore(redis, prefix=f"integration-first-{uuid4()}")
            second_store = RedisHoldStore(redis, prefix=f"integration-second-{uuid4()}")

            first_payment = await create_pending_payment_for_hold(
                session=session,
                store=first_store,
                provider=provider,
                user_id=first_user.id,
                room=room,
                key_suffix="first",
            )
            second_payment = await create_pending_payment_for_hold(
                session=session,
                store=second_store,
                provider=provider,
                user_id=second_user.id,
                room=room,
                key_suffix="second",
            )
            first_payment_id = first_payment.id
            second_payment_id = second_payment.id
            second_order_id = second_payment.order_id
            first_payment = await approve_payment(
                session=session,
                store=first_store,
                provider=provider,
                payment=first_payment,
            )
            second_payment = await approve_payment(
                session=session,
                store=second_store,
                provider=provider,
                payment=second_payment,
            )

            reservation_count = await session.scalar(
                select(func.count())
                .select_from(Reservation)
                .where(Reservation.room_id == room.room_id)
            )
            persisted_first_payment = await session.get(Payment, first_payment_id)
            persisted_second_payment = await session.get(Payment, second_payment_id)
            second_order = await session.get(PaymentOrder, second_order_id)
            assert persisted_first_payment is not None
            assert persisted_second_payment is not None
            assert persisted_first_payment.status == PaymentStatus.APPROVED
            assert persisted_second_payment.status == PaymentStatus.REFUNDED
            assert reservation_count == 1
            assert second_order is not None
            assert second_order.status == PaymentOrderStatus.FAILED
    finally:
        await redis.aclose()
        await engine.dispose()
