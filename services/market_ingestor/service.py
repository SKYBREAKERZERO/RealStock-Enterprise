from __future__ import annotations

from libs.domain.market import (
    MarketQuote,
    MarketTrade,
)
from libs.events import (
    EventEnvelope,
    create_market_quote_event,
    create_market_trade_event,
)
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
    PublishResult,
)


class MarketIngestorService:
    """
    Application service responsible for converting validated
    market-domain objects into canonical events and publishing
    them to the event stream.
    """

    def __init__(
        self,
        producer: KinesisMarketEventProducer
        | None = None,
    ) -> None:
        self._producer = (
            producer
            or KinesisMarketEventProducer()
        )

    def ingest_trade(
        self,
        trade: MarketTrade,
    ) -> PublishResult:
        event = create_market_trade_event(
            trade
        )

        return self._publish_market_event(
            event=event,
            market=trade.market.value,
            symbol=trade.symbol,
        )

    def ingest_quote(
        self,
        quote: MarketQuote,
    ) -> PublishResult:
        event = create_market_quote_event(
            quote
        )

        return self._publish_market_event(
            event=event,
            market=quote.market.value,
            symbol=quote.symbol,
        )

    def _publish_market_event(
        self,
        *,
        event: EventEnvelope,
        market: str,
        symbol: str,
    ) -> PublishResult:
        partition_key = (
            f"{market}:{symbol}"
        )

        return self._producer.publish(
            event,
            partition_key=partition_key,
        )