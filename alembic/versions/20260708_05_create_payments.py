"""create payments

Revision ID: 20260708_05
Revises: 20260708_04
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260708_05"
down_revision: str | Sequence[str] | None = "20260708_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("hourly_rate", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE rooms
        SET hourly_rate = CASE room_type
            WHEN 'vocal' THEN 15000
            WHEN 'band' THEN 30000
            WHEN 'dance' THEN 25000
            ELSE 20000
        END
        """
    )
    op.alter_column("rooms", "hourly_rate", nullable=False)
    op.create_check_constraint(
        op.f("ck_rooms_hourly_rate_positive"),
        "rooms",
        "hourly_rate > 0",
    )

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hold_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payment_orders_amount_positive")),
        sa.CheckConstraint(
            "end_at > start_at",
            name=op.f("ck_payment_orders_end_after_start"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled', 'failed', 'expired')",
            name=op.f("ck_payment_orders_payment_order_status"),
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name=op.f("fk_payment_orders_room_id_rooms"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_payment_orders_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_orders")),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_payment_orders_user_id_idempotency_key",
        ),
    )
    op.create_index(op.f("ix_payment_orders_user_id"), "payment_orders", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount_positive")),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'failed', 'cancelled', 'refunded', "
            "'compensation_pending')",
            name=op.f("ck_payments_payment_status"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["payment_orders.id"],
            name=op.f("fk_payments_order_id_payment_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("order_id", name=op.f("uq_payments_order_id")),
        sa.UniqueConstraint(
            "provider_payment_id",
            name=op.f("uq_payments_provider_payment_id"),
        ),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_event_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_events_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.UniqueConstraint(
            "provider_event_id",
            name=op.f("uq_payment_events_provider_event_id"),
        ),
    )
    op.create_index(
        op.f("ix_payment_events_payment_id"),
        "payment_events",
        ["payment_id"],
    )

    op.add_column("reservations", sa.Column("payment_order_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_reservations_payment_order_id_payment_orders"),
        "reservations",
        "payment_orders",
        ["payment_order_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_reservations_payment_order_id"),
        "reservations",
        ["payment_order_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_reservations_payment_order_id"),
        "reservations",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_reservations_payment_order_id_payment_orders"),
        "reservations",
        type_="foreignkey",
    )
    op.drop_column("reservations", "payment_order_id")
    op.drop_index(op.f("ix_payment_events_payment_id"), table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_table("payments")
    op.drop_index(op.f("ix_payment_orders_user_id"), table_name="payment_orders")
    op.drop_table("payment_orders")
    op.drop_constraint(op.f("ck_rooms_hourly_rate_positive"), "rooms", type_="check")
    op.drop_column("rooms", "hourly_rate")
