import asyncio
import datetime
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.domains.reservations.holds import RedisHoldStore, ReservationHold

pytestmark = pytest.mark.integration


def get_test_settings() -> Settings:
    settings = Settings(_env_file=".env.test")
    if settings.app_env != "test":
        raise RuntimeError("통합 테스트는 APP_ENV=test인 .env.test 또는 환경변수가 필요합니다.")
    return settings


async def test_postgresql_connection() -> None:
    settings = get_test_settings()
    engine = create_async_engine(settings.database_url)

    try:
        async with engine.connect() as connection:
            result = await connection.scalar(text("SELECT 1"))
    finally:
        await engine.dispose()

    assert result == 1


async def test_redis_connection() -> None:
    settings = get_test_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)

    try:
        result = await client.ping()
    finally:
        await client.aclose()

    assert result is True


def make_hold(*, user_id=None, room_id=None) -> ReservationHold:
    now = datetime.datetime.now(datetime.UTC)
    start = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    return ReservationHold(
        id=uuid4(),
        user_id=user_id or uuid4(),
        branch_id=uuid4(),
        room_id=room_id or uuid4(),
        start_at=start,
        end_at=start + datetime.timedelta(hours=1),
        duration_hours=1,
        expires_at=now + datetime.timedelta(seconds=30),
        slot_starts=(start,),
    )


async def test_redis_hold_acquisition_is_atomic() -> None:
    settings = get_test_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    store = RedisHoldStore(client, prefix=f"integration-{uuid4()}")
    room_id = uuid4()
    first = make_hold(room_id=room_id)
    second = make_hold(room_id=room_id)

    try:
        results = await asyncio.gather(
            store.acquire(first, 30),
            store.acquire(second, 30),
        )
        assert sorted(results) == [False, True]
    finally:
        for hold in (first, second):
            await store.release(hold)
        await client.aclose()


async def test_redis_hold_expires_automatically() -> None:
    settings = get_test_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    store = RedisHoldStore(client, prefix=f"integration-{uuid4()}")
    hold = make_hold()

    try:
        assert await store.acquire(hold, 1) is True
        await asyncio.sleep(1.1)
        assert await store.get(hold.id) is None
    finally:
        await store.release(hold)
        await client.aclose()
