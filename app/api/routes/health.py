import asyncio
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.cache.redis import redis_client
from app.database.session import engine

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: ReadinessChecks


DEPENDENCY_CHECK_TIMEOUT_SECONDS = 1.0


async def _check_database() -> bool:
    try:
        async with asyncio.timeout(DEPENDENCY_CHECK_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError):
        return False
    return True


async def _check_redis() -> bool:
    try:
        async with asyncio.timeout(DEPENDENCY_CHECK_TIMEOUT_SECONDS):
            await redis_client.ping()
    except (TimeoutError, RedisError):
        return False
    return True


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """기존 클라이언트를 위한 liveness 호환 엔드포인트."""

    return HealthResponse(status="ok")


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """애플리케이션 프로세스가 요청을 처리할 수 있는지 확인한다."""

    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness() -> ReadinessResponse | JSONResponse:
    """트래픽 처리에 필요한 PostgreSQL과 Redis 연결 상태를 확인한다."""

    database_available, redis_available = await asyncio.gather(
        _check_database(),
        _check_redis(),
    )
    response = ReadinessResponse(
        status="ok" if database_available and redis_available else "unavailable",
        checks=ReadinessChecks(
            database="ok" if database_available else "unavailable",
            redis="ok" if redis_available else "unavailable",
        ),
    )
    if response.status == "unavailable":
        return JSONResponse(status_code=503, content=response.model_dump())
    return response
