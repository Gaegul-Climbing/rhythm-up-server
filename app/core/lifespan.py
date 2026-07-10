from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.cache.redis import close_redis
from app.database.session import engine


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    yield
    await close_redis()
    await engine.dispose()
