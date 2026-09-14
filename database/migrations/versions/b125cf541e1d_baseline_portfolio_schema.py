"""baseline portfolio schema

Revision ID: b125cf541e1d
Revises:
Create Date: 2026-09-14 20:43:39.643485

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b125cf541e1d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial portfolio persistence schema."""

    op.create_table(
        "portfolios",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
    )

    op.create_index(
        "ix_portfolios_user_id",
        "portfolios",
        [
            "user_id",
        ],
        unique=False,
    )

    op.create_table(
        "positions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "portfolio_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "market",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(
                precision=38,
                scale=10,
            ),
            nullable=False,
        ),
        sa.Column(
            "average_cost",
            sa.Numeric(
                precision=38,
                scale=10,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            [
                "portfolio_id",
            ],
            [
                "portfolios.id",
            ],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "portfolio_id",
            "market",
            "symbol",
            name="uq_positions_portfolio_market_symbol",
        ),
    )

    op.create_index(
        "ix_positions_portfolio_id",
        "positions",
        [
            "portfolio_id",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Remove the initial portfolio persistence schema."""

    op.drop_index(
        "ix_positions_portfolio_id",
        table_name="positions",
    )

    op.drop_table(
        "positions",
    )

    op.drop_index(
        "ix_portfolios_user_id",
        table_name="portfolios",
    )

    op.drop_table(
        "portfolios",
    )