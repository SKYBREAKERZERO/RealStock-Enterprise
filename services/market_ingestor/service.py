from __future__ import annotations

import logging

from libs.cache import MarketQuoteCache
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

logger = logging.getLogger(__name__)


class MarketIngestorService:
    """
    Application service responsible for converting validated
    market-domain objects into canonical events and publishing
    them to the event stream.

    Latest quotes are written to Redis only after Kinesis
    publication succeeds.

    Redis is a derived read model and must not determine whether
    the primary event ingestion succeeded.
    """

    def __init__(
        self,
        producer: KinesisMarketEventProducer | None = None,
        quote_cache: MarketQuoteCache | None = None,
    ) -> None:
        self._producer = (
            producer
            if producer is not None
            else KinesisMarketEventProducer()
        )

        self._quote_cache = (
            quote_cache
            if quote_cache is not None
            else MarketQuoteCache()
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

        result = self._publish_market_event(
            event=event,
            market=quote.market.value,
            symbol=quote.symbol,
        )

        self._update_quote_cache(
            quote=quote
        )

        return result

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

    def _update_quote_cache(
        self,
        *,
        quote: MarketQuote,
    ) -> None:
        try:
            self._quote_cache.set_quote(
                quote
            )

        except Exception:
            logger.exception(
                "Failed to update latest quote cache "
                "after successful market event publication: "
                "%s:%s",
                quote.market.value,
                quote.symbol,
            )