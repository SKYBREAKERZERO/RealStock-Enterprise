from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote as url_quote

import httpx

from libs.cache import MarketQuoteCache
from libs.cache.market_quote_cache import (
    MarketQuote as CachedMarketQuote,
)
from libs.domain.market import Market
from libs.trading.market import (
    MarketQuote as TradingMarketQuote,
)


@dataclass(slots=True)
class AlpacaCachedTradingQuoteProvider:
    cache: MarketQuoteCache
    api_key_id: str
    api_secret_key: str
    feed: str = "iex"
    base_url: str = "https://data.alpaca.markets"
    timeout_seconds: float = 5.0
    market: Market = Market.US

    def __post_init__(self) -> None:
        self.api_key_id = self.api_key_id.strip()
        self.api_secret_key = self.api_secret_key.strip()
        self.feed = self.feed.strip().lower()
        self.base_url = self.base_url.rstrip("/")

        if not self.api_key_id:
            raise ValueError(
                "Alpaca API key id must not be empty."
            )

        if not self.api_secret_key:
            raise ValueError(
                "Alpaca API secret key must not be empty."
            )

        if self.feed not in {
            "iex",
            "sip",
            "delayed_sip",
            "boats",
            "overnight",
            "otc",
        }:
            raise ValueError(
                "Unsupported Alpaca stock data feed."
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero"
            )

    def get_quote(
        self,
        symbol: str,
    ) -> TradingMarketQuote:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        cached = self.cache.get_quote(
            market=self.market,
            symbol=normalized_symbol,
        )

        if cached is None:
            cached = self._fetch_and_cache(
                normalized_symbol
            )

        return TradingMarketQuote(
            symbol=cached.symbol,
            bid=cached.bid_price,
            ask=cached.ask_price,
        )

    def refresh_quote(
        self,
        symbol: str,
    ) -> TradingMarketQuote:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        cached = self._fetch_and_cache(
            normalized_symbol
        )

        return TradingMarketQuote(
            symbol=cached.symbol,
            bid=cached.bid_price,
            ask=cached.ask_price,
        )

    def _fetch_and_cache(
        self,
        symbol: str,
    ) -> CachedMarketQuote:
        endpoint = (
            f"{self.base_url}/v2/stocks/"
            f"{url_quote(symbol, safe='')}/quotes/latest"
        )

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
            ) as client:
                response = client.get(
                    endpoint,
                    headers={
                        "APCA-API-KEY-ID": (
                            self.api_key_id
                        ),
                        "APCA-API-SECRET-KEY": (
                            self.api_secret_key
                        ),
                        "Accept": "application/json",
                    },
                    params={
                        "feed": self.feed,
                    },
                )

                response.raise_for_status()
                payload = response.json()

            quote_payload = payload["quote"]

            bid_price = Decimal(
                str(quote_payload["bp"])
            )
            ask_price = Decimal(
                str(quote_payload["ap"])
            )

            bid_size = int(
                quote_payload.get("bs", 0)
            )
            ask_size = int(
                quote_payload.get("as", 0)
            )

            timestamp = self._parse_timestamp(
                quote_payload["t"]
            )

        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
        ) as exc:
            raise self._unavailable_error(
                symbol
            ) from exc

        if (
            bid_price <= Decimal("0")
            or ask_price <= Decimal("0")
            or ask_price < bid_price
        ):
            raise self._unavailable_error(
                symbol
            )

        cached_quote = CachedMarketQuote(
            symbol=symbol,
            market=self.market,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=max(bid_size, 0),
            ask_size=max(ask_size, 0),
            timestamp=timestamp,
        )

        self.cache.set_quote(
            cached_quote
        )

        return cached_quote

    @staticmethod
    def _parse_timestamp(
        value: str,
    ) -> datetime:
        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        return datetime.fromisoformat(
            normalized
        )

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "Symbol must not be empty."
            )

        if len(normalized) > 32:
            raise ValueError(
                "Symbol must not exceed 32 characters."
            )

        return normalized

    @staticmethod
    def _unavailable_error(
        symbol: str,
    ) -> ValueError:
        return ValueError(
            "No current bid/ask market quote "
            f"available for {symbol}."
        )
