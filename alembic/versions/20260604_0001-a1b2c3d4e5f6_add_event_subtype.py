"""add event_subtype column to events table

Revision ID: a1b2c3d4e5f6
Revises: 49b0509b6388
Create Date: 2026-06-04 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "49b0509b6388"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("event_subtype", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_events_event_subtype",
        "events",
        ["event_subtype"],
    )


def downgrade() -> None:
    op.drop_index("ix_events_event_subtype", table_name="events")
    op.drop_column("events", "event_subtype")
