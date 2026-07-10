import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PaymentOrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    COMPENSATION_PENDING = "compensation_pending"


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_payment_orders_user_id_idempotency_key",
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("end_at > start_at", name="end_after_start"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    hold_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    room_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_hours: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KRW")
    status: Mapped[PaymentOrderStatus] = mapped_column(
        Enum(
            PaymentOrderStatus,
            name="payment_order_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=PaymentOrderStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("payment_orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    amount: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
