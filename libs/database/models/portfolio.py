from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from libs.database.models.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class PortfolioModel(Base):
    __tablename__ = "portfolios"

    __table_args__ = (
        Index(
            "ix_portfolios_user_id",
            "user_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
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

    positions: Mapped[list[PositionModel]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PositionModel(Base):
    __tablename__ = "positions"

    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "market",
            "symbol",
            name="uq_positions_portfolio_market_symbol",
        ),
        Index(
            "ix_positions_portfolio_id",
            "portfolio_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "portfolios.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    market: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=38,
            scale=10,
        ),
        nullable=False,
    )

    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=38,
            scale=10,
        ),
        nullable=False,
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

    portfolio: Mapped[PortfolioModel] = relationship(
        back_populates="positions",
    )