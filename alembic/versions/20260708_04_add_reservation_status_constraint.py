"""add reservation status constraint

Revision ID: 20260708_04
Revises: 20260708_03
Create Date: 2026-07-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260708_04"
down_revision: str | Sequence[str] | None = "20260708_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_reservations_reservation_status"),
        "reservations",
        "status IN ('confirmed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_reservations_reservation_status"),
        "reservations",
        type_="check",
    )
