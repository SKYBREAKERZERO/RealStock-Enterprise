from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from libs.database.models.watchlist import (
    WatchlistItemModel,
)
from libs.database.repositories.watchlist import (
    WatchlistRepository,
)

_SYMBOL_PATTERN = re.compile(
    r"^[A-Z0-9.^-]{1,20}$"
)


class WatchlistError(RuntimeError):
    pass


class InvalidWatchlistSymbolError(
    WatchlistError
):
    pass


class WatchlistItemAlreadyExistsError(
    WatchlistError
):
    pass


class WatchlistItemNotFoundError(
    WatchlistError
):
    pass


class WatchlistLimitExceededError(
    WatchlistError
):
    pass


class WatchlistService:
    """
    Application service for persistent user watchlists.

    Transaction boundary:
        service owns commit / rollback
        repository owns persistence operations
    """

    def __init__(
        self,
        session: Session,
        *,
        max_items: int,
    ) -> None:
        if max_items <= 0:
            raise ValueError(
                "max_items must be greater than zero"
            )

        self._session = session

        self._repository = (
            WatchlistRepository(
                session
            )
        )

        self._max_items = max_items

    @staticmethod
    def normalize_symbol(
        symbol: str,
    ) -> str:
        normalized = (
            symbol
            .strip()
            .upper()
        )

        if not normalized:
            raise InvalidWatchlistSymbolError(
                "symbol must not be empty"
            )

        if not _SYMBOL_PATTERN.fullmatch(
            normalized
        ):
            raise InvalidWatchlistSymbolError(
                "invalid symbol format"
            )

        return normalized

    def list_items(
        self,
        *,
        user_id: str,
    ) -> list[WatchlistItemModel]:
        return (
            self._repository
            .list_for_user(
                user_id=user_id,
            )
        )

    def add_item(
        self,
        *,
        user_id: str,
        symbol: str,
    ) -> WatchlistItemModel:
        normalized = (
            self.normalize_symbol(
                symbol
            )
        )

        existing = (
            self._repository
            .get_by_user_and_symbol(
                user_id=user_id,
                symbol=normalized,
            )
        )

        if existing is not None:
            raise WatchlistItemAlreadyExistsError(
                "symbol already exists in watchlist"
            )

        count = (
            self._repository
            .count_for_user(
                user_id=user_id,
            )
        )

        if count >= self._max_items:
            raise WatchlistLimitExceededError(
                "watchlist item limit exceeded"
            )

        try:
            model = (
                self._repository
                .add(
                    user_id=user_id,
                    symbol=normalized,
                )
            )

            self._session.commit()

        except IntegrityError as exc:
            self._session.rollback()

            raise (
                WatchlistItemAlreadyExistsError(
                    "symbol already exists in watchlist"
                )
            ) from exc

        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(
            model
        )

        return model

    def delete_item(
        self,
        *,
        user_id: str,
        symbol: str,
    ) -> None:
        normalized = (
            self.normalize_symbol(
                symbol
            )
        )

        try:
            deleted = (
                self._repository
                .delete(
                    user_id=user_id,
                    symbol=normalized,
                )
            )

            if not deleted:
                self._session.rollback()

                raise WatchlistItemNotFoundError(
                    "watchlist item not found"
                )

            self._session.commit()

        except WatchlistItemNotFoundError:
            raise

        except Exception:
            self._session.rollback()
            raise