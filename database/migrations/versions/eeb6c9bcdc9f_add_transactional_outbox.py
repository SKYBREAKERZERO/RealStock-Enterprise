"""add transactional outbox

Revision ID: eeb6c9bcdc9f
Revises: b125cf541e1d
Create Date: 2026-09-18 20:29:00.607916
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "eeb6c9bcdc9f"
down_revision: str | Sequence[str] | None = "b125cf541e1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "aggregate_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "aggregate_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "correlation_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "causation_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column(
            "trace_context",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
        sa.UniqueConstraint(
            "event_id"
        ),
    )

    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        [
            "aggregate_type",
            "aggregate_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        [
            "published_at",
            "occurred_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_outbox_events_pending",
        table_name="outbox_events",
    )

    op.drop_index(
        "ix_outbox_events_aggregate",
        table_name="outbox_events",
    )

    op.drop_table(
        "outbox_events"
    )