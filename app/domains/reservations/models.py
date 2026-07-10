import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ReservationStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_reservations_user_id_idempotency_key",
        ),
        CheckConstraint("end_at > start_at", name="end_after_start"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="reservation_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ReservationStatus.CONFIRMED,
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payment_order_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("payment_orders.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )

    slots: Mapped[list["ReservationSlot"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
    )


class ReservationSlot(Base):
    __tablename__ = "reservation_slots"
    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "start_at",
            name="uq_reservation_slots_room_id_start_at",
        ),
        UniqueConstraint(
            "user_id",
            "start_at",
            name="uq_reservation_slots_user_id_start_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reservation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reservation: Mapped[Reservation] = relationship(back_populates="slots")
