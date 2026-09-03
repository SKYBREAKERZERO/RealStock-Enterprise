from __future__ import annotations

from uuid import UUID

from libs.domain.market import MarketQuote, MarketTrade
from libs.events.envelope import EventEnvelope


MARKET_TRADE_RECEIVED = "market.trade.received"
MARKET_QUOTE_RECEIVED = "market.quote.received"

MARKET_EVENT_SCHEMA_VERSION = 1

MARKET_INGESTOR_SOURCE = "market-ingestor"


def create_market_trade_event(
    trade: MarketTrade,
    *,
    source: str = MARKET_INGESTOR_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope:
    """
    Convert a MarketTrade domain object into the canonical
    market.trade.received event contract.

    The transport/event layer receives only serialized domain data.
    It does not contain boto3, Kinesis, FastAPI, SQLAlchemy, or
    infrastructure-specific logic.
    """

    kwargs: dict[str, object] = {
        "event_type": MARKET_TRADE_RECEIVED,
        "schema_version": MARKET_EVENT_SCHEMA_VERSION,
        "occurred_at": trade.timestamp,
        "source": source,
        "causation_id": causation_id,
        "payload": trade.model_dump(
            mode="json",
        ),
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id

    return EventEnvelope(**kwargs)


def create_market_quote_event(
    quote: MarketQuote,
    *,
    source: str = MARKET_INGESTOR_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope:
    """
    Convert a MarketQuote domain object into the canonical
    market.quote.received event contract.
    """

    kwargs: dict[str, object] = {
        "event_type": MARKET_QUOTE_RECEIVED,
        "schema_version": MARKET_EVENT_SCHEMA_VERSION,
        "occurred_at": quote.timestamp,
        "source": source,
        "causation_id": causation_id,
        "payload": quote.model_dump(
            mode="json",
        ),
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id

    return EventEnvelope(**kwargs)