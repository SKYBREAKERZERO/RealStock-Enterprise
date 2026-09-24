from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.models.base import Base

MONEY_PRECISION = 20
MONEY_SCALE = 6


def utc_now() -> datetime:
    return datetime.now(UTC)


class PaperAccountModel(Base):
    __tablename__ = "paper_accounts"

    __table_args__ = (
        CheckConstraint(
            "initial_cash > 0",
            name="ck_paper_accounts_initial_cash_positive",
        ),
        CheckConstraint(
            "cash_balance >= 0",
            name="ck_paper_accounts_cash_balance_non_negative",
        ),
        Index(
            "ix_paper_accounts_user_id",
            "user_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    initial_cash: Mapped[Decimal] = mapped_column(
        Numeric(
            MONEY_PRECISION,
            MONEY_SCALE,
        ),
        nullable=False,
    )

    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(
            MONEY_PRECISION,
            MONEY_SCALE,
        ),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class PaperPositionModel(Base):
    __tablename__ = "paper_positions"

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name="ck_paper_positions_quantity_non_negative",
        ),
        CheckConstraint(
            "average_cost >= 0",
            name="ck_paper_positions_average_cost_non_negative",
        ),
        UniqueConstraint(
            "account_id",
            "symbol",
            name="uq_paper_positions_account_symbol",
        ),
        Index(
            "ix_paper_positions_account_id",
            "account_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "paper_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(
            MONEY_PRECISION,
            MONEY_SCALE,
        ),
        nullable=False,
        default=Decimal("0"),
    )

    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(
            MONEY_PRECISION,
            MONEY_SCALE,
        ),
        nullable=False,
        default=Decimal("0"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class PaperOrderModel(Base):
    __tablename__ = "paper_orders"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_paper_orders_quantity_positive",
        ),
        CheckConstraint(
            "filled_quantity >= 0",
            name="ck_paper_orders_filled_quantity_non_negative",
        ),
        CheckConstraint(
            "filled_quantity <= quantity",
            name="ck_paper_orders_fill_not_over_quantity",
        ),
        Index(
            "ix_paper_orders_account_id",
            "account_id",
        ),
        Index(
            "ix_paper_orders_account_status",
            "account_id",
            "status",
        ),
        Index(
            "ix_paper_orders_symbol_status",
            "symbol",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "paper_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    side: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    order_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    filled_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    limit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(
            MONEY_PRECISION,
            MONEY_SCALE,
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class PaperExecutionModel(Base):
    __tablename__ = "paper_executions"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_paper_executions_quantity_positive",
        ),
        CheckConstraint(
            "price > 0",
            name="ck_paper_executions_price_positive",
        ),
        Index(
            "ix_paper_executions_order_id",
            "order_id",
        ),
        Index(
            "ix_paper_executions_account_id",
            "account_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "paper_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "paper_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    side: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(
            MONEY_PRECISION,
            MONEY_SCALE,
        ),
        nullable=False,
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )