import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.payments.models import PaymentOrderStatus, PaymentStatus


class PaymentOrderCreateRequest(BaseModel):
    hold_id: UUID


class PaymentOrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    hold_id: UUID
    room_id: UUID
    start_at: datetime.datetime
    end_at: datetime.datetime
    duration_hours: int
    amount: int
    currency: str
    status: PaymentOrderStatus
    expires_at: datetime.datetime
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentCreateRequest(BaseModel):
    order_id: UUID


class PaymentCheckoutResponse(BaseModel):
    provider: str
    client_key: str
    order_id: str
    order_name: str
    amount: int
    currency: str
    success_url: str
    fail_url: str


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    provider: str
    provider_payment_id: str
    amount: int
    status: PaymentStatus
    failure_code: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    checkout: PaymentCheckoutResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class TossPaymentConfirmRequest(BaseModel):
    payment_key: str
    order_id: UUID
    amount: int


class MockPaymentOutcome(StrEnum):
    APPROVED = "approved"
    FAILED = "failed"


class MockPaymentCompleteRequest(BaseModel):
    outcome: MockPaymentOutcome
    deliver_event: bool = True


class MockPaymentCompleteResponse(BaseModel):
    provider_payment_id: str
    provider_status: str
    event_id: str
    event_delivered: bool
    payment: PaymentResponse
