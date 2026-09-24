from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from libs.trading.enums import (
    OrderSide,
    OrderType,
)
from libs.trading.execution import Execution
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from libs.trading.paper_broker import PaperBroker
from services.trading.models import (
    TradeExecutionResult,
)
from services.trading.quote_service import QuoteService


@dataclass(slots=True)
class PaperTradingService:
    """
    Application service for paper-trading operations.

    Responsibilities:
    - Retrieve the latest normalized bid/ask quote.
    - Create domain orders.
    - Delegate execution semantics to PaperBroker.
    - Return complete order/execution results.

    Persistence and transaction boundaries are deliberately handled
    by a higher-level persistent application service.
    """

    quote_service: QuoteService
    broker: PaperBroker

    # ==========================================================
    # MARKET orders
    # ==========================================================

    def market_buy(
        self,
        *,
        account: PaperAccount,
        position: Position,
        quantity: int,
    ) -> TradeExecutionResult:
        """
        Execute a MARKET BUY using the current ask price.
        """

        order = PaperOrder(
            account_id=account.account_id,
            symbol=position.symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.MARKET,
        )

        quote = self.quote_service.get_quote(
            position.symbol
        )

        execution = self.broker.execute_market_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )

        return TradeExecutionResult(
            order=order,
            execution=execution,
        )

    def market_sell(
        self,
        *,
        account: PaperAccount,
        position: Position,
        quantity: int,
    ) -> TradeExecutionResult:
        """
        Execute a MARKET SELL using the current bid price.
        """

        order = PaperOrder(
            account_id=account.account_id,
            symbol=position.symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=OrderType.MARKET,
        )

        quote = self.quote_service.get_quote(
            position.symbol
        )

        execution = self.broker.execute_market_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )

        return TradeExecutionResult(
            order=order,
            execution=execution,
        )

    # ==========================================================
    # LIMIT order submission
    # ==========================================================

    def submit_limit_buy(
        self,
        *,
        account: PaperAccount,
        position: Position,
        quantity: int,
        limit_price: Decimal,
    ) -> PaperOrder:
        """
        Submit a LIMIT BUY order.

        Submission places the order into PENDING state.
        Execution occurs later when the live ask price reaches
        or falls below the configured limit price.
        """

        order = PaperOrder(
            account_id=account.account_id,
            symbol=position.symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
        )

        quote = self.quote_service.get_quote(
            position.symbol
        )

        self.broker.submit_limit_order(
            order=order,
            position=position,
            quote=quote,
        )

        return order

    def submit_limit_sell(
        self,
        *,
        account: PaperAccount,
        position: Position,
        quantity: int,
        limit_price: Decimal,
    ) -> PaperOrder:
        """
        Submit a LIMIT SELL order.

        Submission places the order into PENDING state.
        Execution occurs later when the live bid price reaches
        or exceeds the configured limit price.
        """

        order = PaperOrder(
            account_id=account.account_id,
            symbol=position.symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
        )

        quote = self.quote_service.get_quote(
            position.symbol
        )

        self.broker.submit_limit_order(
            order=order,
            position=position,
            quote=quote,
        )

        return order

    # ==========================================================
    # LIMIT order processing
    # ==========================================================

    def process_limit_order(
        self,
        *,
        account: PaperAccount,
        position: Position,
        order: PaperOrder,
    ) -> Execution | None:
        """
        Re-evaluate a pending LIMIT order against the latest quote.

        Returns an Execution when the order is triggered.
        Returns None when the order remains pending or cannot
        currently be executed.
        """

        quote = self.quote_service.get_quote(
            order.symbol
        )

        return self.broker.process_quote(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )

    # ==========================================================
    # Cancellation
    # ==========================================================

    def cancel_order(
        self,
        *,
        order: PaperOrder,
    ) -> None:
        """
        Cancel an eligible paper order.
        """

        self.broker.cancel_order(
            order=order,
        )