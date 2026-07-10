import asyncio
import datetime
from uuid import UUID, uuid4

from app.domains.payments.providers.base import (
    ProviderEvent,
    ProviderPayment,
    ProviderPaymentStatus,
)
from app.domains.reservations.holds import ReservationHold


class MemoryHoldStore:
    def __init__(self) -> None:
        self._holds: dict[UUID, ReservationHold] = {}
        self._users: dict[UUID, UUID] = {}
        self._slots: dict[tuple[UUID, datetime.datetime], UUID] = {}
        self._lock = asyncio.Lock()

    def _purge_expired(self) -> None:
        now = datetime.datetime.now(datetime.UTC)
        expired = [hold for hold in self._holds.values() if hold.expires_at <= now]
        for hold in expired:
            self._release(hold)

    def _release(self, hold: ReservationHold) -> None:
        self._holds.pop(hold.id, None)
        if self._users.get(hold.user_id) == hold.id:
            self._users.pop(hold.user_id, None)
        for slot in hold.slot_starts:
            key = (hold.room_id, slot)
            if self._slots.get(key) == hold.id:
                self._slots.pop(key, None)

    async def acquire(self, hold: ReservationHold, ttl_seconds: int) -> bool:
        del ttl_seconds
        async with self._lock:
            self._purge_expired()
            if hold.user_id in self._users:
                return False
            if any((hold.room_id, slot) in self._slots for slot in hold.slot_starts):
                return False
            self._holds[hold.id] = hold
            self._users[hold.user_id] = hold.id
            for slot in hold.slot_starts:
                self._slots[(hold.room_id, slot)] = hold.id
            return True

    async def get(self, hold_id: UUID) -> ReservationHold | None:
        async with self._lock:
            self._purge_expired()
            return self._holds.get(hold_id)

    async def release(self, hold: ReservationHold) -> None:
        async with self._lock:
            self._release(hold)

    async def busy_slots(
        self,
        room_id: UUID,
        slot_starts: tuple[datetime.datetime, ...],
    ) -> set[datetime.datetime]:
        async with self._lock:
            self._purge_expired()
            return {slot for slot in slot_starts if (room_id, slot) in self._slots}


class MemoryPaymentProvider:
    name = "memory"

    def __init__(self) -> None:
        self.payments: dict[str, ProviderPayment] = {}

    async def create_payment(self, order_id: UUID, amount: int) -> ProviderPayment:
        payment = ProviderPayment(
            f"memory_{uuid4().hex}", order_id, amount, ProviderPaymentStatus.PENDING
        )
        self.payments[payment.id] = payment
        return payment

    async def get_payment(self, payment_id: str) -> ProviderPayment | None:
        return self.payments.get(payment_id)

    async def complete_payment(
        self, payment_id: str, status: ProviderPaymentStatus
    ) -> ProviderEvent:
        payment = self.payments[payment_id]
        event_id = payment.terminal_event_id or f"memory_event_{uuid4().hex}"
        payment = ProviderPayment(
            payment.id,
            payment.order_id,
            payment.amount,
            status,
            event_id,
            "mock_payment_failed" if status == ProviderPaymentStatus.FAILED else None,
        )
        self.payments[payment.id] = payment
        return ProviderEvent(
            event_id,
            payment.id,
            payment.order_id,
            payment.amount,
            payment.status,
            payment.failure_code,
        )

    async def cancel_payment(self, payment_id: str) -> ProviderPayment:
        payment = self.payments[payment_id]
        cancelled = ProviderPayment(
            payment.id,
            payment.order_id,
            payment.amount,
            ProviderPaymentStatus.CANCELLED,
            payment.terminal_event_id,
            payment.failure_code,
        )
        self.payments[payment_id] = cancelled
        return cancelled
