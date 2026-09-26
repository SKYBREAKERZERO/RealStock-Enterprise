from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from libs.database.unit_of_work import UnitOfWork
from libs.trading.models import PaperAccount


class TradingAccountAlreadyExistsError(ValueError):
    pass


@dataclass(slots=True)
class TradingAccountService:
    unit_of_work: UnitOfWork

    def open_account(
        self,
        *,
        user_id: str,
        initial_cash: Decimal,
    ) -> PaperAccount:
        normalized_user_id = user_id.strip()

        if not normalized_user_id:
            raise ValueError("user_id must not be empty")

        if initial_cash <= 0:
            raise ValueError("initial_cash must be greater than zero")

        with self.unit_of_work:
            existing = (
                self.unit_of_work
                .paper_accounts
                .get_by_user_id(
                    normalized_user_id
                )
            )

            if existing is not None:
                raise TradingAccountAlreadyExistsError(
                    "paper account already exists"
                )

            account = PaperAccount(
                initial_cash=initial_cash,
            )

            self.unit_of_work.paper_accounts.add(
                user_id=normalized_user_id,
                account=account,
            )

            self.unit_of_work.commit()

            return account
