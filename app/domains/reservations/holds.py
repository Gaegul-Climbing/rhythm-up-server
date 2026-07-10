import datetime
import json
from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

ACQUIRE_HOLD_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 then
    return 0
end
for index = 3, #KEYS do
    if redis.call('EXISTS', KEYS[index]) == 1 then
        return 0
    end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
for index = 3, #KEYS do
    redis.call('SET', KEYS[index], ARGV[1], 'EX', ARGV[3])
end
return 1
"""

RELEASE_HOLD_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('DEL', KEYS[1])
end
redis.call('DEL', KEYS[2])
for index = 3, #KEYS do
    if redis.call('GET', KEYS[index]) == ARGV[1] then
        redis.call('DEL', KEYS[index])
    end
end
return 1
"""


@dataclass(frozen=True)
class ReservationHold:
    id: UUID
    user_id: UUID
    branch_id: UUID
    room_id: UUID
    start_at: datetime.datetime
    end_at: datetime.datetime
    duration_hours: int
    expires_at: datetime.datetime
    slot_starts: tuple[datetime.datetime, ...]

    def to_json(self) -> str:
        value = asdict(self)
        for key in ("id", "user_id", "branch_id", "room_id"):
            value[key] = str(value[key])
        for key in ("start_at", "end_at", "expires_at"):
            value[key] = value[key].isoformat()
        value["slot_starts"] = [slot.isoformat() for slot in self.slot_starts]
        return json.dumps(value, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "ReservationHold":
        value = json.loads(raw)
        return cls(
            id=UUID(value["id"]),
            user_id=UUID(value["user_id"]),
            branch_id=UUID(value["branch_id"]),
            room_id=UUID(value["room_id"]),
            start_at=datetime.datetime.fromisoformat(value["start_at"]),
            end_at=datetime.datetime.fromisoformat(value["end_at"]),
            duration_hours=value["duration_hours"],
            expires_at=datetime.datetime.fromisoformat(value["expires_at"]),
            slot_starts=tuple(
                datetime.datetime.fromisoformat(slot) for slot in value["slot_starts"]
            ),
        )


class HoldStore(Protocol):
    async def acquire(self, hold: ReservationHold, ttl_seconds: int) -> bool: ...

    async def get(self, hold_id: UUID) -> ReservationHold | None: ...

    async def release(self, hold: ReservationHold) -> None: ...

    async def busy_slots(
        self,
        room_id: UUID,
        slot_starts: tuple[datetime.datetime, ...],
    ) -> set[datetime.datetime]: ...


class RedisHoldStore:
    def __init__(self, client: Redis, prefix: str) -> None:
        self.client = client
        self.prefix = prefix

    def user_key(self, user_id: UUID) -> str:
        return f"{self.prefix}:reservation-holds:user:{user_id}"

    def record_key(self, hold_id: UUID) -> str:
        return f"{self.prefix}:reservation-holds:id:{hold_id}"

    def slot_key(self, room_id: UUID, start_at: datetime.datetime) -> str:
        return f"{self.prefix}:reservation-holds:room:{room_id}:slot:{int(start_at.timestamp())}"

    async def acquire(self, hold: ReservationHold, ttl_seconds: int) -> bool:
        keys = [
            self.user_key(hold.user_id),
            self.record_key(hold.id),
            *(self.slot_key(hold.room_id, slot) for slot in hold.slot_starts),
        ]
        result = await self.client.eval(
            ACQUIRE_HOLD_SCRIPT,
            len(keys),
            *keys,
            str(hold.id),
            hold.to_json(),
            ttl_seconds,
        )
        return bool(result)

    async def get(self, hold_id: UUID) -> ReservationHold | None:
        raw = await self.client.get(self.record_key(hold_id))
        if raw is None:
            return None
        return ReservationHold.from_json(raw)

    async def release(self, hold: ReservationHold) -> None:
        keys = [
            self.user_key(hold.user_id),
            self.record_key(hold.id),
            *(self.slot_key(hold.room_id, slot) for slot in hold.slot_starts),
        ]
        await self.client.eval(RELEASE_HOLD_SCRIPT, len(keys), *keys, str(hold.id))

    async def busy_slots(
        self,
        room_id: UUID,
        slot_starts: tuple[datetime.datetime, ...],
    ) -> set[datetime.datetime]:
        if not slot_starts:
            return set()
        values = await self.client.mget([self.slot_key(room_id, slot) for slot in slot_starts])
        return {slot for slot, value in zip(slot_starts, values, strict=True) if value is not None}
