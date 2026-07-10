from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ProviderPaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ProviderPayment:
    id: str
    order_id: UUID
    amount: int
    status: ProviderPaymentStatus
    terminal_event_id: str | None = None
    failure_code: str | None = None


@dataclass(frozen=True)
class ProviderEvent:
    id: str
    payment_id: str
    order_id: UUID
    amount: int
    status: ProviderPaymentStatus
    failure_code: str | None = None

    @property
    def event_type(self) -> str:
        return f"payment.{self.status.value}"

    def as_payload(self) -> dict[str, str | int | None]:
        return {
            "event_id": self.id,
            "payment_id": self.payment_id,
            "order_id": str(self.order_id),
            "amount": self.amount,
            "status": self.status.value,
            "failure_code": self.failure_code,
        }


class PaymentProvider(Protocol):
    name: str

    async def create_payment(self, order_id: UUID, amount: int) -> ProviderPayment: ...

    async def get_payment(self, payment_id: str) -> ProviderPayment | None: ...

    async def cancel_payment(self, payment_id: str) -> ProviderPayment: ...


class ControllablePaymentProvider(PaymentProvider, Protocol):
    async def complete_payment(
        self,
        payment_id: str,
        status: ProviderPaymentStatus,
    ) -> ProviderEvent: ...
