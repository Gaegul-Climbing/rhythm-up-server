import json
from dataclasses import asdict
from uuid import UUID, uuid4

from redis.asyncio import Redis

from app.domains.payments.providers.base import (
    ProviderEvent,
    ProviderPayment,
    ProviderPaymentStatus,
)


class LocalPaymentProvider:
    name = "local"

    def __init__(self, client: Redis, prefix: str, ttl_seconds: int) -> None:
        self.client = client
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds

    def payment_key(self, payment_id: str) -> str:
        return f"{self.prefix}:local-payment-provider:payments:{payment_id}"

    async def _save(self, payment: ProviderPayment) -> None:
        value = asdict(payment)
        value["order_id"] = str(payment.order_id)
        value["status"] = payment.status.value
        await self.client.set(
            self.payment_key(payment.id),
            json.dumps(value, separators=(",", ":")),
            ex=self.ttl_seconds,
        )

    async def create_payment(self, order_id: UUID, amount: int) -> ProviderPayment:
        payment = ProviderPayment(
            id=f"local_{uuid4().hex}",
            order_id=order_id,
            amount=amount,
            status=ProviderPaymentStatus.PENDING,
        )
        await self._save(payment)
        return payment

    async def get_payment(self, payment_id: str) -> ProviderPayment | None:
        raw = await self.client.get(self.payment_key(payment_id))
        if raw is None:
            return None
        value = json.loads(raw)
        return ProviderPayment(
            id=value["id"],
            order_id=UUID(value["order_id"]),
            amount=value["amount"],
            status=ProviderPaymentStatus(value["status"]),
            terminal_event_id=value.get("terminal_event_id"),
            failure_code=value.get("failure_code"),
        )

    async def complete_payment(
        self,
        payment_id: str,
        status: ProviderPaymentStatus,
    ) -> ProviderEvent:
        if status not in (ProviderPaymentStatus.APPROVED, ProviderPaymentStatus.FAILED):
            raise ValueError("Local payment can only be approved or failed")
        payment = await self.get_payment(payment_id)
        if payment is None:
            raise KeyError(payment_id)
        if payment.status == ProviderPaymentStatus.PENDING:
            payment = ProviderPayment(
                id=payment.id,
                order_id=payment.order_id,
                amount=payment.amount,
                status=status,
                terminal_event_id=f"local_event_{uuid4().hex}",
                failure_code="mock_payment_failed"
                if status == ProviderPaymentStatus.FAILED
                else None,
            )
            await self._save(payment)
        if payment.terminal_event_id is None:
            raise ValueError("Terminal payment has no event id")
        return ProviderEvent(
            id=payment.terminal_event_id,
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            status=payment.status,
            failure_code=payment.failure_code,
        )

    async def cancel_payment(self, payment_id: str) -> ProviderPayment:
        payment = await self.get_payment(payment_id)
        if payment is None:
            raise KeyError(payment_id)
        cancelled = ProviderPayment(
            id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            status=ProviderPaymentStatus.CANCELLED,
            terminal_event_id=payment.terminal_event_id,
            failure_code=payment.failure_code,
        )
        await self._save(cancelled)
        return cancelled
