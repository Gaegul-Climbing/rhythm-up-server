from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

redis_client: Redis = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


async def get_redis() -> Redis:
    """FastAPI 의존성으로 공유 Redis 클라이언트를 제공한다."""

    return redis_client


async def close_redis() -> None:
    await redis_client.aclose()
