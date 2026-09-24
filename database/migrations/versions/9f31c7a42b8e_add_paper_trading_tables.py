from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f31c7a42b8e"
down_revision: str | None = "f80dd8819e17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
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
            "initial_cash",
            sa.Numeric(
                precision=20,
                scale=6,
            ),
            nullable=False,
        ),
        sa.Column(
            "cash_balance",
            sa.Numeric(
                precision=20,
                scale=6,
            ),
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
        sa.CheckConstraint(
            "initial_cash > 0",
            name=(
                "ck_paper_accounts_"
                "initial_cash_positive"
            ),
        ),
        sa.CheckConstraint(
            "cash_balance >= 0",
            name=(
                "ck_paper_accounts_"
                "cash_balance_non_negative"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
    )

    op.create_index(
        "ix_paper_accounts_user_id",
        "paper_accounts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "paper_positions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "average_cost",
            sa.Numeric(
                precision=20,
                scale=6,
            ),
            nullable=False,
        ),
        sa.Column(
            "realized_pnl",
            sa.Numeric(
                precision=20,
                scale=6,
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
        sa.CheckConstraint(
            "quantity >= 0",
            name=(
                "ck_paper_positions_"
                "quantity_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "average_cost >= 0",
            name=(
                "ck_paper_positions_"
                "average_cost_non_negative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["paper_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "account_id",
            "symbol",
            name=(
                "uq_paper_positions_"
                "account_symbol"
            ),
        ),
    )

    op.create_index(
        "ix_paper_positions_account_id",
        "paper_positions",
        ["account_id"],
        unique=False,
    )

    op.create_table(
        "paper_orders",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "side",
            sa.String(length=8),
            nullable=False,
        ),
        sa.Column(
            "order_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "filled_quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "limit_price",
            sa.Numeric(
                precision=20,
                scale=6,
            ),
            nullable=True,
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
        sa.CheckConstraint(
            "quantity > 0",
            name=(
                "ck_paper_orders_"
                "quantity_positive"
            ),
        ),
        sa.CheckConstraint(
            "filled_quantity >= 0",
            name=(
                "ck_paper_orders_"
                "filled_quantity_non_negative"
            ),
        ),
        sa.CheckConstraint(
            "filled_quantity <= quantity",
            name=(
                "ck_paper_orders_"
                "fill_not_over_quantity"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["paper_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
    )

    op.create_index(
        "ix_paper_orders_account_id",
        "paper_orders",
        ["account_id"],
        unique=False,
    )

    op.create_index(
        "ix_paper_orders_account_status",
        "paper_orders",
        [
            "account_id",
            "status",
        ],
        unique=False,
    )

    op.create_index(
        "ix_paper_orders_symbol_status",
        "paper_orders",
        [
            "symbol",
            "status",
        ],
        unique=False,
    )

    op.create_table(
        "paper_executions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "side",
            sa.String(length=8),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(
                precision=20,
                scale=6,
            ),
            nullable=False,
        ),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name=(
                "ck_paper_executions_"
                "quantity_positive"
            ),
        ),
        sa.CheckConstraint(
            "price > 0",
            name=(
                "ck_paper_executions_"
                "price_positive"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["paper_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["paper_orders.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
    )

    op.create_index(
        "ix_paper_executions_account_id",
        "paper_executions",
        ["account_id"],
        unique=False,
    )

    op.create_index(
        "ix_paper_executions_order_id",
        "paper_executions",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_executions_order_id",
        table_name="paper_executions",
    )

    op.drop_index(
        "ix_paper_executions_account_id",
        table_name="paper_executions",
    )

    op.drop_table(
        "paper_executions"
    )

    op.drop_index(
        "ix_paper_orders_symbol_status",
        table_name="paper_orders",
    )

    op.drop_index(
        "ix_paper_orders_account_status",
        table_name="paper_orders",
    )

    op.drop_index(
        "ix_paper_orders_account_id",
        table_name="paper_orders",
    )

    op.drop_table(
        "paper_orders"
    )

    op.drop_index(
        "ix_paper_positions_account_id",
        table_name="paper_positions",
    )

    op.drop_table(
        "paper_positions"
    )

    op.drop_index(
        "ix_paper_accounts_user_id",
        table_name="paper_accounts",
    )

    op.drop_table(
        "paper_accounts"
    )