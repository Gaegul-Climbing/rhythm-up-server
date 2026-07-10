"""create branches and rooms

Revision ID: 20260708_02
Revises: 20260706_01
Create Date: 2026-07-08
"""

import datetime
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260708_02"
down_revision: str | Sequence[str] | None = "20260706_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GANGNAM_BRANCH_ID = UUID("10000000-0000-0000-0000-000000000001")
HONGDAE_BRANCH_ID = UUID("10000000-0000-0000-0000-000000000002")
SEONGSU_BRANCH_ID = UUID("10000000-0000-0000-0000-000000000003")


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("status", sa.String(length=18), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'temporarily_closed', 'closed')",
            name=op.f("ck_branches_branch_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
        sa.UniqueConstraint("slug", name=op.f("uq_branches_slug")),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("room_type", sa.String(length=6), nullable=False),
        sa.Column("recommended_capacity", sa.Integer(), nullable=False),
        sa.Column("max_capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=11), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_capacity >= recommended_capacity",
            name=op.f("ck_rooms_max_capacity_not_less_than_recommended"),
        ),
        sa.CheckConstraint(
            "recommended_capacity >= 1",
            name=op.f("ck_rooms_recommended_capacity_positive"),
        ),
        sa.CheckConstraint(
            "room_type IN ('vocal', 'band', 'dance')",
            name=op.f("ck_rooms_room_type"),
        ),
        sa.CheckConstraint(
            "status IN ('available', 'maintenance', 'inactive')",
            name=op.f("ck_rooms_room_status"),
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_rooms_branch_id_branches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sa.UniqueConstraint("branch_id", "name", name="uq_rooms_branch_id_name"),
    )
    op.create_index(op.f("ix_rooms_branch_id"), "rooms", ["branch_id"], unique=False)

    branches = sa.table(
        "branches",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("address", sa.String()),
        sa.column("phone", sa.String()),
        sa.column("opens_at", sa.Time()),
        sa.column("closes_at", sa.Time()),
        sa.column("status", sa.String()),
    )
    op.bulk_insert(
        branches,
        [
            {
                "id": GANGNAM_BRANCH_ID,
                "name": "리듬업 연습실 강남점",
                "slug": "gangnam",
                "address": "서울특별시 강남구 테헤란로 100",
                "phone": "02-1000-1001",
                "opens_at": datetime.time(9, 0),
                "closes_at": datetime.time(0, 0),
                "status": "open",
            },
            {
                "id": HONGDAE_BRANCH_ID,
                "name": "리듬업 연습실 홍대점",
                "slug": "hongdae",
                "address": "서울특별시 마포구 양화로 100",
                "phone": "02-1000-1002",
                "opens_at": datetime.time(9, 0),
                "closes_at": datetime.time(0, 0),
                "status": "open",
            },
            {
                "id": SEONGSU_BRANCH_ID,
                "name": "리듬업 연습실 성수점",
                "slug": "seongsu",
                "address": "서울특별시 성동구 연무장길 100",
                "phone": "02-1000-1003",
                "opens_at": datetime.time(9, 0),
                "closes_at": datetime.time(0, 0),
                "status": "temporarily_closed",
            },
        ],
    )

    rooms = sa.table(
        "rooms",
        sa.column("id", sa.Uuid()),
        sa.column("branch_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("room_type", sa.String()),
        sa.column("recommended_capacity", sa.Integer()),
        sa.column("max_capacity", sa.Integer()),
        sa.column("status", sa.String()),
    )
    op.bulk_insert(
        rooms,
        [
            {
                "id": UUID("20000000-0000-0000-0000-000000000001"),
                "branch_id": GANGNAM_BRANCH_ID,
                "name": "보컬 A",
                "room_type": "vocal",
                "recommended_capacity": 1,
                "max_capacity": 2,
                "status": "available",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000002"),
                "branch_id": GANGNAM_BRANCH_ID,
                "name": "밴드 A",
                "room_type": "band",
                "recommended_capacity": 4,
                "max_capacity": 6,
                "status": "available",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000003"),
                "branch_id": GANGNAM_BRANCH_ID,
                "name": "댄스 A",
                "room_type": "dance",
                "recommended_capacity": 4,
                "max_capacity": 8,
                "status": "maintenance",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000004"),
                "branch_id": HONGDAE_BRANCH_ID,
                "name": "보컬 A",
                "room_type": "vocal",
                "recommended_capacity": 1,
                "max_capacity": 2,
                "status": "available",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000005"),
                "branch_id": HONGDAE_BRANCH_ID,
                "name": "밴드 A",
                "room_type": "band",
                "recommended_capacity": 4,
                "max_capacity": 6,
                "status": "available",
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000006"),
                "branch_id": SEONGSU_BRANCH_ID,
                "name": "댄스 A",
                "room_type": "dance",
                "recommended_capacity": 4,
                "max_capacity": 8,
                "status": "available",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rooms_branch_id"), table_name="rooms")
    op.drop_table("rooms")
    op.drop_table("branches")
