from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db_session
from app.domains.payments.dependencies import (
    get_controllable_payment_provider,
    get_payment_provider,
)
from app.domains.reservations.dependencies import get_hold_store
from app.main import create_app
from tests.fakes import MemoryHoldStore, MemoryPaymentProvider


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def hold_store() -> MemoryHoldStore:
    return MemoryHoldStore()


@pytest_asyncio.fixture
async def payment_provider() -> MemoryPaymentProvider:
    return MemoryPaymentProvider()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    hold_store: MemoryHoldStore,
    payment_provider: MemoryPaymentProvider,
) -> AsyncIterator[AsyncClient]:
    application = create_app()

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = override_db_session
    application.dependency_overrides[get_hold_store] = lambda: hold_store
    application.dependency_overrides[get_payment_provider] = lambda: payment_provider
    application.dependency_overrides[get_controllable_payment_provider] = lambda: payment_provider
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
