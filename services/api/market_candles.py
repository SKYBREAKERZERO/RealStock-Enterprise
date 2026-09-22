from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from redis.exceptions import RedisError
from services.api.market_candle_cache import (
    MarketCandleCache,
)

from services.api.schemas.market import (
    MarketCandleItem,
    MarketCandleRange,
    MarketCandlesResponse,
)
from services.market_ingestor.providers.twelve_data import (
    TwelveDataMarketDataProvider,
    TwelveDataRequestError,
    TwelveDataResponseError,
)


@dataclass(
    frozen=True,
    slots=True,
)
class MarketCandleCachePolicy:
    """
    Fresh/stale Redis TTL policy for one candlestick range.
    """

    fresh_ttl_seconds: int
    stale_ttl_seconds: int

    def __post_init__(
        self,
    ) -> None:
        if (
            self.fresh_ttl_seconds
            <= 0
        ):
            raise ValueError(
                "fresh_ttl_seconds must be "
                "greater than zero"
            )

        if (
            self.stale_ttl_seconds
            <= self.fresh_ttl_seconds
        ):
            raise ValueError(
                "stale_ttl_seconds must be "
                "greater than fresh_ttl_seconds"
            )


class MarketCandleService:
    """
    Resolve market candlesticks with Redis resilience.

    Read path:

        fresh Redis
            ↓ miss / Redis unavailable
        Twelve Data
            ↓ success
        populate fresh + stale Redis

    Failure path:

        Twelve Data failure
            ↓
        stale Redis
            ↓
        return stale data when available

    Redis itself is treated as an optimization and resilience layer.
    A Redis outage must not prevent a successful provider response
    from reaching the API caller.
    """

    def __init__(
        self,
        *,
        provider: TwelveDataMarketDataProvider,
        cache: MarketCandleCache,
        cache_policies: Mapping[
            MarketCandleRange,
            MarketCandleCachePolicy,
        ],
    ) -> None:
        self._provider = (
            provider
        )

        self._cache = (
            cache
        )

        self._cache_policies = (
            dict(
                cache_policies
            )
        )

        required_ranges: tuple[
            MarketCandleRange,
            ...,
        ] = (
            "day",
            "week",
            "month",
        )

        missing_ranges = [
            range_value
            for range_value
            in required_ranges
            if (
                range_value
                not in self._cache_policies
            )
        ]

        if missing_ranges:
            raise ValueError(
                
                    "Missing candle cache "
                    "policies: "
                    + ", ".join(
                        missing_ranges
                    )
                
            )

    def _get_fresh(
        self,
        *,
        symbol: str,
        range_value: MarketCandleRange,
    ) -> MarketCandlesResponse | None:
        try:
            return (
                self._cache
                .get_fresh(
                    symbol=symbol,
                    range_value=(
                        range_value
                    ),
                )
            )

        except RedisError:
            return None

    def _get_stale(
        self,
        *,
        symbol: str,
        range_value: MarketCandleRange,
    ) -> MarketCandlesResponse | None:
        try:
            return (
                self._cache
                .get_stale(
                    symbol=symbol,
                    range_value=(
                        range_value
                    ),
                )
            )

        except RedisError:
            return None

    def _write_cache(
        self,
        response: MarketCandlesResponse,
    ) -> None:
        policy = (
            self._cache_policies[
                response.range
            ]
        )

        try:
            self._cache.set_candles(
                response,
                fresh_ttl_seconds=(
                    policy
                    .fresh_ttl_seconds
                ),
                stale_ttl_seconds=(
                    policy
                    .stale_ttl_seconds
                ),
            )

        except RedisError:
            return

    def get_candles(
        self,
        *,
        symbol: str,
        range_value: MarketCandleRange,
        interval: str,
        outputsize: int,
    ) -> MarketCandlesResponse:
        fresh = (
            self._get_fresh(
                symbol=symbol,
                range_value=(
                    range_value
                ),
            )
        )

        if fresh is not None:
            return fresh

        try:
            candles = (
                self._provider
                .get_time_series(
                    symbol,
                    interval=interval,
                    outputsize=(
                        outputsize
                    ),
                )
            )

            response = (
                MarketCandlesResponse(
                    symbol=symbol,
                    range=range_value,
                    interval=interval,
                    items=[
                        MarketCandleItem(
                            time=(
                                candle.datetime
                            ),
                            open=float(
                                candle.open
                            ),
                            high=float(
                                candle.high
                            ),
                            low=float(
                                candle.low
                            ),
                            close=float(
                                candle.close
                            ),
                        )
                        for candle
                        in candles
                    ],
                )
            )

        except (
            TwelveDataRequestError,
            TwelveDataResponseError,
        ):
            stale = (
                self._get_stale(
                    symbol=symbol,
                    range_value=(
                        range_value
                    ),
                )
            )

            if stale is not None:
                return stale

            raise

        self._write_cache(
            response
        )

        return response