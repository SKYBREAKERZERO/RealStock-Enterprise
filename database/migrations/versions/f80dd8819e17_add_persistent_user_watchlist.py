"""add persistent user watchlist

Revision ID: f80dd8819e17
Revises: 9be7d5328b5f
Create Date: 2026-09-20 10:41:27.678842

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f80dd8819e17"
down_revision: str | Sequence[str] | None = "9be7d5328b5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "watchlist_items",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "user_id",
            "symbol",
            name="uq_watchlist_items_user_symbol",
        ),
    )

    op.create_index(
        "ix_watchlist_items_user_created_at",
        "watchlist_items",
        [
            "user_id",
            "created_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_watchlist_items_user_created_at",
        table_name="watchlist_items",
    )

    op.drop_table(
        "watchlist_items"
    )