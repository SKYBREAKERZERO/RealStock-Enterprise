from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from redis import Redis

from libs.cache.redis_client import get_redis_client
from libs.domain.market import (
    Market,
    MarketQuote,
)


DEFAULT_QUOTE_TTL_SECONDS = 30

QUOTE_KEY_PREFIX = "realstock:quote"


class MarketQuoteCache:
    """
    Redis-backed latest market quote cache.

    Redis is an ephemeral read model, not the system of record.
    Quotes always expire to prevent stale market data from being
    treated as current data.
    """

    def __init__(
        self,
        redis_client: Redis | None = None,
        *,
        ttl_seconds: int = DEFAULT_QUOTE_TTL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError(
                "ttl_seconds must be greater than zero"
            )

        self._redis = (
            redis_client
            if redis_client is not None
            else get_redis_client()
        )

        self._ttl_seconds = ttl_seconds

    @staticmethod
    def build_key(
        *,
        market: Market,
        symbol: str,
    ) -> str:
        normalized_symbol = (
            symbol
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        if len(normalized_symbol) > 32:
            raise ValueError(
                "symbol must not exceed 32 characters"
            )

        return (
            f"{QUOTE_KEY_PREFIX}:"
            f"{market.value}:"
            f"{normalized_symbol}"
        )

    def set_quote(
        self,
        quote: MarketQuote,
    ) -> None:
        key = self.build_key(
            market=quote.market,
            symbol=quote.symbol,
        )

        payload = {
            "symbol": quote.symbol,
            "market": quote.market.value,
            "bid_price": str(
                quote.bid_price
            ),
            "ask_price": str(
                quote.ask_price
            ),
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "timestamp": (
                quote.timestamp
                .isoformat()
            ),
        }

        self._redis.set(
            key,
            json.dumps(
                payload,
                separators=(",", ":"),
            ),
            ex=self._ttl_seconds,
        )

    def get_quote(
        self,
        *,
        market: Market,
        symbol: str,
    ) -> MarketQuote | None:
        key = self.build_key(
            market=market,
            symbol=symbol,
        )

        raw = self._redis.get(
            key
        )

        if raw is None:
            return None

        payload = json.loads(
            raw
        )

        return MarketQuote(
            symbol=payload["symbol"],
            market=Market(
                payload["market"]
            ),
            bid_price=Decimal(
                payload["bid_price"]
            ),
            ask_price=Decimal(
                payload["ask_price"]
            ),
            bid_size=int(
                payload["bid_size"]
            ),
            ask_size=int(
                payload["ask_size"]
            ),
            timestamp=datetime.fromisoformat(
                payload["timestamp"]
            ),
        )

    def delete_quote(
        self,
        *,
        market: Market,
        symbol: str,
    ) -> bool:
        key = self.build_key(
            market=market,
            symbol=symbol,
        )

        deleted = self._redis.delete(
            key
        )

        return deleted > 0