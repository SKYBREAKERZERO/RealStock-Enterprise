from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from libs.database.unit_of_work import UnitOfWork
from libs.trading.execution import Execution
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)


@dataclass(slots=True)
class TradingQueryService:
    unit_of_work: UnitOfWork

    def get_account(
        self,
        *,
        user_id: str,
    ) -> PaperAccount | None:
        with self.unit_of_work:
            return (
                self.unit_of_work
                .paper_accounts
                .get_by_user_id(
                    user_id
                )
            )

    def get_order(
        self,
        *,
        user_id: str,
        order_id: UUID,
    ) -> PaperOrder | None:
        with self.unit_of_work:
            account_id = (
                self._require_account_id_for_user(
                    user_id
                )
            )

            order = (
                self.unit_of_work
                .paper_orders
                .get(
                    order_id
                )
            )

            if order is None:
                return None

            if order.account_id != account_id:
                return None

            return order

    def list_positions(
        self,
        *,
        user_id: str,
    ) -> list[Position]:
        with self.unit_of_work:
            account_id = (
                self._require_account_id_for_user(
                    user_id
                )
            )

            return (
                self.unit_of_work
                .paper_positions
                .list_by_account(
                    account_id
                )
            )

    def list_orders(
        self,
        *,
        user_id: str,
        limit: int = 100,
    ) -> list[PaperOrder]:
        with self.unit_of_work:
            account_id = (
                self._require_account_id_for_user(
                    user_id
                )
            )

            return (
                self.unit_of_work
                .paper_orders
                .list_by_account(
                    account_id,
                    limit=limit,
                )
            )

    def list_open_orders(
        self,
        *,
        user_id: str,
        limit: int = 100,
    ) -> list[PaperOrder]:
        with self.unit_of_work:
            account_id = (
                self._require_account_id_for_user(
                    user_id
                )
            )

            return (
                self.unit_of_work
                .paper_orders
                .list_open_by_account(
                    account_id,
                    limit=limit,
                )
            )

    def list_executions(
        self,
        *,
        user_id: str,
        limit: int = 100,
    ) -> list[Execution]:
        with self.unit_of_work:
            account_id = (
                self._require_account_id_for_user(
                    user_id
                )
            )

            return (
                self.unit_of_work
                .paper_executions
                .list_by_account(
                    account_id,
                    limit=limit,
                )
            )

    def _require_account_id_for_user(
        self,
        user_id: str,
    ) -> UUID:
        account = (
            self.unit_of_work
            .paper_accounts
            .get_by_user_id(
                user_id
            )
        )

        if account is None:
            raise ValueError(
                "Paper account for user "
                f"{user_id!r} not found."
            )

        account_id = account.account_id

        if account_id is None:
            raise RuntimeError(
                "Persisted paper account must have "
                "an account_id."
            )

        return account_id
