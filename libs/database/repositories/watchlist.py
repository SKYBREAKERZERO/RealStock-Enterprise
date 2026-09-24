from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from libs.database.models.watchlist import (
    WatchlistItemModel,
)


class WatchlistRepository:
    """
    SQLAlchemy persistence adapter for user watchlists.

    Repository methods flush but never commit.
    Transaction ownership belongs to the application service.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def list_for_user(
        self,
        *,
        user_id: str,
    ) -> list[WatchlistItemModel]:
        statement = (
            select(
                WatchlistItemModel
            )
            .where(
                WatchlistItemModel.user_id
                == user_id
            )
            .order_by(
                WatchlistItemModel.created_at.asc(),
                WatchlistItemModel.symbol.asc(),
            )
        )

        return list(
            self._session
            .scalars(
                statement
            )
            .all()
        )

    def count_for_user(
        self,
        *,
        user_id: str,
    ) -> int:
        statement = (
            select(
                func.count(
                    WatchlistItemModel.id
                )
            )
            .where(
                WatchlistItemModel.user_id
                == user_id
            )
        )

        return int(
            self._session.scalar(
                statement
            )
            or 0
        )

    def get_by_user_and_symbol(
        self,
        *,
        user_id: str,
        symbol: str,
    ) -> WatchlistItemModel | None:
        statement = (
            select(
                WatchlistItemModel
            )
            .where(
                WatchlistItemModel.user_id
                == user_id,
                WatchlistItemModel.symbol
                == symbol,
            )
        )

        return (
            self._session
            .scalars(
                statement
            )
            .one_or_none()
        )

    def add(
        self,
        *,
        user_id: str,
        symbol: str,
    ) -> WatchlistItemModel:
        model = WatchlistItemModel(
            user_id=user_id,
            symbol=symbol,
        )

        self._session.add(
            model
        )

        self._session.flush()

        return model

    def delete(
        self,
        *,
        user_id: str,
        symbol: str,
    ) -> bool:
        model = (
            self.get_by_user_and_symbol(
                user_id=user_id,
                symbol=symbol,
            )
        )

        if model is None:
            return False

        self._session.delete(
            model
        )

        self._session.flush()

        return True