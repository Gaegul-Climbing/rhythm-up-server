from typing import Annotated

from fastapi import Depends

from app.cache.redis import redis_client
from app.core.config import get_settings
from app.domains.reservations.holds import HoldStore, RedisHoldStore

settings = get_settings()
hold_store = RedisHoldStore(redis_client, settings.redis_key_prefix)


def get_hold_store() -> HoldStore:
    return hold_store


HoldStoreDependency = Annotated[HoldStore, Depends(get_hold_store)]
