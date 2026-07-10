import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class BranchStatus(StrEnum):
    OPEN = "open"
    TEMPORARILY_CLOSED = "temporarily_closed"
    CLOSED = "closed"


class RoomType(StrEnum):
    VOCAL = "vocal"
    BAND = "band"
    DANCE = "dance"


class RoomStatus(StrEnum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    opens_at: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    status: Mapped[BranchStatus] = mapped_column(
        Enum(
            BranchStatus,
            name="branch_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=BranchStatus.OPEN,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    rooms: Mapped[list["Room"]] = relationship(back_populates="branch")


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("branch_id", "name", name="uq_rooms_branch_id_name"),
        CheckConstraint(
            "recommended_capacity >= 1",
            name="recommended_capacity_positive",
        ),
        CheckConstraint(
            "max_capacity >= recommended_capacity",
            name="max_capacity_not_less_than_recommended",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    branch_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[RoomType] = mapped_column(
        Enum(
            RoomType,
            name="room_type",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    recommended_capacity: Mapped[int] = mapped_column(nullable=False)
    max_capacity: Mapped[int] = mapped_column(nullable=False)
    hourly_rate: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(
            RoomStatus,
            name="room_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=RoomStatus.AVAILABLE,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    branch: Mapped[Branch] = relationship(back_populates="rooms")
