"""create reservations

Revision ID: 20260708_03
Revises: 20260708_02
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260708_03"
down_revision: str | Sequence[str] | None = "20260708_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_reservations_end_after_start")),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name=op.f("fk_reservations_room_id_rooms"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_reservations_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservations")),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_reservations_user_id_idempotency_key",
        ),
    )
    op.create_index(op.f("ix_reservations_room_id"), "reservations", ["room_id"])
    op.create_index(op.f("ix_reservations_user_id"), "reservations", ["user_id"])

    op.create_table(
        "reservation_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
            name=op.f("fk_reservation_slots_reservation_id_reservations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name=op.f("fk_reservation_slots_room_id_rooms"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_reservation_slots_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservation_slots")),
        sa.UniqueConstraint(
            "room_id",
            "start_at",
            name="uq_reservation_slots_room_id_start_at",
        ),
        sa.UniqueConstraint(
            "user_id",
            "start_at",
            name="uq_reservation_slots_user_id_start_at",
        ),
    )
    op.create_index(
        op.f("ix_reservation_slots_reservation_id"),
        "reservation_slots",
        ["reservation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reservation_slots_reservation_id"),
        table_name="reservation_slots",
    )
    op.drop_table("reservation_slots")
    op.drop_index(op.f("ix_reservations_user_id"), table_name="reservations")
    op.drop_index(op.f("ix_reservations_room_id"), table_name="reservations")
    op.drop_table("reservations")
