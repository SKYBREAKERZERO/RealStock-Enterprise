from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from libs.trading.execution import Execution
from libs.trading.models import PaperOrder
from services.trading.models import TradeExecutionResult
from services.trading.persistent_paper_trading_service import (
    PersistentPaperTradingService,
)
from services.trading.trading_query_service import TradingQueryService


class TradingWriteAccountNotFoundError(ValueError):
    pass


class TradingWriteOrderNotFoundError(ValueError):
    pass


@dataclass(slots=True)
class TradingWriteService:
    query_service: TradingQueryService
    persistent_service: PersistentPaperTradingService

    def market_buy(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: int,
    ) -> TradeExecutionResult:
        return self.persistent_service.market_buy(
            account_id=self._account_id(user_id),
            symbol=symbol,
            quantity=quantity,
        )

    def market_sell(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: int,
    ) -> TradeExecutionResult:
        return self.persistent_service.market_sell(
            account_id=self._account_id(user_id),
            symbol=symbol,
            quantity=quantity,
        )

    def submit_limit_buy(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: int,
        limit_price: Decimal,
    ) -> PaperOrder:
        return self.persistent_service.submit_limit_buy(
            account_id=self._account_id(user_id),
            symbol=symbol,
            quantity=quantity,
            limit_price=limit_price,
        )

    def submit_limit_sell(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: int,
        limit_price: Decimal,
    ) -> PaperOrder:
        return self.persistent_service.submit_limit_sell(
            account_id=self._account_id(user_id),
            symbol=symbol,
            quantity=quantity,
            limit_price=limit_price,
        )

    def cancel_limit_order(
        self,
        *,
        user_id: str,
        order_id: UUID,
    ) -> PaperOrder:
        self._owned_order(user_id=user_id, order_id=order_id)
        return self.persistent_service.cancel_limit_order(
            order_id=order_id,
        )

    def process_limit_order(
        self,
        *,
        user_id: str,
        order_id: UUID,
    ) -> Execution | None:
        self._owned_order(user_id=user_id, order_id=order_id)
        return self.persistent_service.process_limit_order(
            order_id=order_id,
        )

    def _account_id(self, user_id: str) -> UUID:
        account = self.query_service.get_account(user_id=user_id)

        if account is None:
            raise TradingWriteAccountNotFoundError(
                "paper account not found"
            )

        if account.account_id is None:
            raise RuntimeError(
                "Persisted paper account must have an account_id."
            )

        return account.account_id

    def _owned_order(
        self,
        *,
        user_id: str,
        order_id: UUID,
    ) -> PaperOrder:
        self._account_id(user_id)

        order = self.query_service.get_order(
            user_id=user_id,
            order_id=order_id,
        )

        if order is None:
            raise TradingWriteOrderNotFoundError(
                "paper order not found"
            )

        return order
