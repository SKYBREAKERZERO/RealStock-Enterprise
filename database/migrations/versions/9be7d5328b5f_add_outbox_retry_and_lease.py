"""add outbox retry and lease

Revision ID: 9be7d5328b5f
Revises: eeb6c9bcdc9f
Create Date: 2026-09-19 10:11:45.665432

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9be7d5328b5f"
down_revision: str | Sequence[str] | None = "eeb6c9bcdc9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add retry scheduling and dispatcher lease fields."""

    op.add_column(
        "outbox_events",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(
                timezone=True,
            ),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
    )

    op.add_column(
        "outbox_events",
        sa.Column(
            "locked_until",
            sa.DateTime(
                timezone=True,
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "outbox_events",
        sa.Column(
            "locked_by",
            sa.String(
                length=128,
            ),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_outbox_events_dispatchable",
        "outbox_events",
        [
            "published_at",
            "next_attempt_at",
            "occurred_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Remove retry scheduling and dispatcher lease fields."""

    op.drop_index(
        "ix_outbox_events_dispatchable",
        table_name="outbox_events",
    )

    op.drop_column(
        "outbox_events",
        "locked_by",
    )

    op.drop_column(
        "outbox_events",
        "locked_until",
    )

    op.drop_column(
        "outbox_events",
        "next_attempt_at",
    )