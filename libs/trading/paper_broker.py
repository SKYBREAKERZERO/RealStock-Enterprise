from __future__ import annotations

from libs.trading.enums import OrderSide, OrderStatus, OrderType
from libs.trading.execution import Execution
from libs.trading.market import MarketQuote
from libs.trading.models import PaperAccount, PaperOrder, Position


class PaperBroker:
    def execute_market_order(
        self,
        *,
        account: PaperAccount,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> Execution:
        self._validate_common(
            order=order,
            position=position,
            quote=quote,
        )

        if order.order_type != OrderType.MARKET:
            raise ValueError(
                "Order must be MARKET."
            )

        order.mark_pending()

        return self._fill_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )

    def submit_limit_order(
        self,
        *,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> None:
        self._validate_common(
            order=order,
            position=position,
            quote=quote,
        )

        if order.order_type != OrderType.LIMIT:
            raise ValueError(
                "Order must be LIMIT."
            )

        order.mark_pending()

    def process_quote(
        self,
        *,
        account: PaperAccount,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> Execution | None:
        if order.order_type != OrderType.LIMIT:
            raise ValueError(
                "process_quote supports LIMIT orders only."
            )

        if order.status != OrderStatus.PENDING:
            return None

        if order.symbol != quote.symbol:
            raise ValueError(
                "Order symbol does not match market quote symbol."
            )

        if order.symbol != position.symbol:
            raise ValueError(
                "Order symbol does not match position symbol."
            )

        if not self._limit_is_triggered(
            order=order,
            quote=quote,
        ):
            return None

        return self._fill_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )

    def cancel_order(
        self,
        *,
        order: PaperOrder,
    ) -> None:
        order.cancel()

    def _validate_common(
        self,
        *,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> None:
        if order.status != OrderStatus.NEW:
            raise ValueError(
                "Only NEW orders can be submitted."
            )

        if order.symbol != quote.symbol:
            raise ValueError(
                "Order symbol does not match market quote symbol."
            )

        if order.symbol != position.symbol:
            raise ValueError(
                "Order symbol does not match position symbol."
            )

    def _limit_is_triggered(
        self,
        *,
        order: PaperOrder,
        quote: MarketQuote,
    ) -> bool:
        if order.limit_price is None:
            raise ValueError(
                "LIMIT order must define limit price."
            )

        if order.side == OrderSide.BUY:
            return quote.ask <= order.limit_price

        if order.side == OrderSide.SELL:
            return quote.bid >= order.limit_price

        raise ValueError(
            f"Unsupported order side: {order.side}"
        )

    def _fill_order(
        self,
        *,
        account: PaperAccount,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> Execution:
        if order.side == OrderSide.BUY:
            return self._execute_buy(
                account=account,
                order=order,
                position=position,
                quote=quote,
            )

        if order.side == OrderSide.SELL:
            return self._execute_sell(
                account=account,
                order=order,
                position=position,
                quote=quote,
            )

        raise ValueError(
            f"Unsupported order side: {order.side}"
        )

    def _execute_buy(
        self,
        *,
        account: PaperAccount,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> Execution:
        execution_price = quote.ask
        quantity = order.remaining_quantity

        account.ensure_can_buy(
            quantity=quantity,
            estimated_price=execution_price,
        )

        total_cost = execution_price * quantity

        account.debit(total_cost)

        position.buy(
            quantity=quantity,
            price=execution_price,
        )

        order.record_fill(quantity)

        return Execution(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=execution_price,
        )

    def _execute_sell(
        self,
        *,
        account: PaperAccount,
        order: PaperOrder,
        position: Position,
        quote: MarketQuote,
    ) -> Execution:
        execution_price = quote.bid
        quantity = order.remaining_quantity

        position.sell(
            quantity=quantity,
            price=execution_price,
        )

        proceeds = execution_price * quantity

        account.credit(proceeds)

        order.record_fill(quantity)

        return Execution(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=execution_price,
        )