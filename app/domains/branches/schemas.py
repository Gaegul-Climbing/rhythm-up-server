import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.branches.models import BranchStatus, RoomStatus, RoomType


class BranchResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    address: str
    phone: str
    opens_at: datetime.time
    closes_at: datetime.time
    status: BranchStatus

    model_config = ConfigDict(from_attributes=True)


class RoomResponse(BaseModel):
    id: UUID
    branch_id: UUID
    name: str
    room_type: RoomType
    recommended_capacity: int
    max_capacity: int
    hourly_rate: int
    status: RoomStatus

    model_config = ConfigDict(from_attributes=True)
