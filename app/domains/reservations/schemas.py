import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.reservations.models import ReservationStatus


class AvailabilitySlotResponse(BaseModel):
    start_at: datetime.datetime
    end_at: datetime.datetime
    available: bool


class AvailabilityResponse(BaseModel):
    room_id: UUID
    date: datetime.date
    timezone: str
    slots: list[AvailabilitySlotResponse]


class HoldCreateRequest(BaseModel):
    branch_id: UUID
    room_id: UUID
    start_at: datetime.datetime
    duration_hours: int = Field(ge=1, le=4)


class HoldResponse(BaseModel):
    id: UUID
    user_id: UUID
    branch_id: UUID
    room_id: UUID
    start_at: datetime.datetime
    end_at: datetime.datetime
    duration_hours: int
    expires_at: datetime.datetime


class ReservationCreateRequest(BaseModel):
    hold_id: UUID


class ReservationResponse(BaseModel):
    id: UUID
    user_id: UUID
    room_id: UUID
    start_at: datetime.datetime
    end_at: datetime.datetime
    status: ReservationStatus
    created_at: datetime.datetime
    cancelled_at: datetime.datetime | None

    model_config = ConfigDict(from_attributes=True)
