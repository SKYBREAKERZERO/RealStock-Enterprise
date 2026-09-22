from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from services.market_ingestor.providers.twelve_data import (
    TwelveDataQuoteSnapshot,
)

MarketCandleRange = Literal[
    "day",
    "week",
    "month",
]


class FiftyTwoWeekRangeResponse(
    BaseModel
):
    low: Decimal
    high: Decimal

    low_change: Decimal
    high_change: Decimal

    low_change_percent: Decimal
    high_change_percent: Decimal

    range: str


class MarketPriceResponse(
    BaseModel
):
    symbol: str
    price: Decimal


class MarketQuoteResponse(
    BaseModel
):
    symbol: str
    name: str

    exchange: str
    mic_code: str
    currency: str

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    previous_close: Decimal

    change: Decimal
    percent_change: Decimal

    volume: int
    average_volume: int

    is_market_open: bool

    timestamp: datetime

    last_quote_at: (
        datetime
        | None
    ) = None

    fifty_two_week: (
        FiftyTwoWeekRangeResponse
        | None
    ) = None

    @classmethod
    def from_snapshot(
        cls,
        snapshot: TwelveDataQuoteSnapshot,
    ) -> MarketQuoteResponse:
        fifty_two_week = None

        if (
            snapshot.fifty_two_week
            is not None
        ):
            value = (
                snapshot
                .fifty_two_week
            )

            fifty_two_week = (
                FiftyTwoWeekRangeResponse(
                    low=value.low,
                    high=value.high,
                    low_change=(
                        value.low_change
                    ),
                    high_change=(
                        value.high_change
                    ),
                    low_change_percent=(
                        value
                        .low_change_percent
                    ),
                    high_change_percent=(
                        value
                        .high_change_percent
                    ),
                    range=value.range,
                )
            )

        return cls(
            symbol=snapshot.symbol,
            name=snapshot.name,
            exchange=(
                snapshot.exchange
            ),
            mic_code=(
                snapshot.mic_code
            ),
            currency=(
                snapshot.currency
            ),
            open=snapshot.open,
            high=snapshot.high,
            low=snapshot.low,
            close=snapshot.close,
            previous_close=(
                snapshot
                .previous_close
            ),
            change=(
                snapshot.change
            ),
            percent_change=(
                snapshot
                .percent_change
            ),
            volume=(
                snapshot.volume
            ),
            average_volume=(
                snapshot
                .average_volume
            ),
            is_market_open=(
                snapshot
                .is_market_open
            ),
            timestamp=(
                snapshot.timestamp
            ),
            last_quote_at=(
                snapshot
                .last_quote_at
            ),
            fifty_two_week=(
                fifty_two_week
            ),
        )


class MarketBatchQuoteItem(
    BaseModel
):
    symbol: str

    status: Literal[
        "ok",
        "stale",
        "error",
    ]

    source: Literal[
        "provider",
        "cache",
        "stale_cache",
    ] | None = None

    quote: (
        MarketQuoteResponse
        | None
    ) = None

    error: str | None = None


class MarketBatchQuoteResponse(
    BaseModel
):
    requested: int
    succeeded: int
    stale: int
    failed: int

    items: list[
        MarketBatchQuoteItem
    ]


class MarketCandleItem(
    BaseModel
):
    """
    One normalized OHLC candlestick returned by the market API.

    Provider-side Decimal values are converted to JSON-compatible
    floating-point numbers at the API boundary for direct consumption
    by the frontend charting library.
    """

    time: str

    open: float
    high: float
    low: float
    close: float


class MarketCandlesResponse(
    BaseModel
):
    """
    Candlestick series for one symbol and one display range.

    range:
        day
            Intraday five-minute candles.

        week
            Hourly candles.

        month
            Daily candles.
    """

    symbol: str

    range: MarketCandleRange

    interval: str

    items: list[
        MarketCandleItem
    ]