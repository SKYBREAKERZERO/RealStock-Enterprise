from __future__ import annotations

from libs.domain.market import (
    MarketQuote,
)
from libs.domain.risk import (
    PriceMoveRule,
)
from libs.events import (
    MARKET_QUOTE_RECEIVED,
    EventEnvelope,
    create_risk_alert_event,
)
from services.risk_engine.state import (
    InMemoryQuoteStateStore,
    QuoteStateStore,
)


class RiskEngineService:
    def __init__(
        self,
        *,
        price_move_rule: PriceMoveRule | None = None,
        state_store: QuoteStateStore | None = None,
    ) -> None:
        self._price_move_rule = (
            price_move_rule
            if price_move_rule is not None
            else PriceMoveRule()
        )

        self._state_store = (
            state_store
            if state_store is not None
            else InMemoryQuoteStateStore()
        )

    def process_event(
        self,
        event: EventEnvelope,
    ) -> EventEnvelope | None:
        """
        Process one canonical market event.

        Non-quote events are ignored because the shared market
        stream may contain both trade and quote events.
        """

        if (
            event.event_type
            != MARKET_QUOTE_RECEIVED
        ):
            return None

        current_quote = (
            MarketQuote.model_validate(
                event.payload
            )
        )

        previous_quote = (
            self._state_store.get_quote(
                market=current_quote.market,
                symbol=current_quote.symbol,
            )
        )

        # First quote initializes keyed state.
        if previous_quote is None:
            self._state_store.set_quote(
                current_quote
            )

            return None

        # Do not allow delayed/out-of-order events to move
        # processing state backwards.
        if (
            current_quote.timestamp
            <= previous_quote.timestamp
        ):
            return None

        alert = (
            self._price_move_rule.evaluate(
                previous_quote=previous_quote,
                current_quote=current_quote,
            )
        )

        # State advances even when there is no alert.
        # The next comparison is always against the most
        # recently processed valid quote.
        self._state_store.set_quote(
            current_quote
        )

        if alert is None:
            return None

        return create_risk_alert_event(
            alert,
            correlation_id=(
                event.correlation_id
            ),
            causation_id=(
                event.event_id
            ),
        )