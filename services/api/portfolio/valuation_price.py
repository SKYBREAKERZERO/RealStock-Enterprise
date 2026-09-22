from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from libs.domain.market import Market


@dataclass(
    frozen=True,
    slots=True,
)
class ValuationInstrument:
    """
    Instrument identity required for portfolio valuation.

    Market remains part of the identity even though the current
    batch market API is symbol-oriented.
    """

    market: Market
    symbol: str

    def __post_init__(
        self,
    ) -> None:
        normalized_symbol = (
            self.symbol
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        object.__setattr__(
            self,
            "symbol",
            normalized_symbol,
        )

    @property
    def key(
        self,
    ) -> tuple[
        Market,
        str,
    ]:
        return (
            self.market,
            self.symbol,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ValuationPrice:
    """
    Explicit market price used for valuation.

    This intentionally does not pretend to be a bid/ask
    MarketQuote.
    """

    market: Market
    symbol: str

    price: Decimal
    timestamp: datetime

    stale: bool = False

    @property
    def key(
        self,
    ) -> tuple[
        Market,
        str,
    ]:
        return (
            self.market,
            self.symbol,
        )


class SnapshotQuote(
    Protocol
):
    close: Decimal
    timestamp: datetime


class BatchQuoteItem(
    Protocol
):
    symbol: str
    status: str
    quote: SnapshotQuote | None


class BatchQuoteResponse(
    Protocol
):
    items: list[BatchQuoteItem]


class BatchQuoteReader(
    Protocol
):
    def get_quotes(
        self,
        symbols: list[str],
    ) -> BatchQuoteResponse:
        ...


class ValuationPriceSource(
    Protocol
):
    def get_prices(
        self,
        instruments: tuple[
            ValuationInstrument,
            ...
        ],
    ) -> dict[
        tuple[
            Market,
            str,
        ],
        ValuationPrice,
    ]:
        ...


class BatchMarketValuationPriceSource:
    """
    Adapter from the batch OHLC market-data service to explicit
    portfolio valuation prices.

    Valuation policy:
    - Twelve Data snapshot close is the valuation price.
    - stale-cache snapshots remain usable valuation prices.
    - error results remain missing prices.
    - bid/ask MarketQuote semantics are never fabricated.
    """

    def __init__(
        self,
        batch_service: BatchQuoteReader,
    ) -> None:
        self._batch_service = (
            batch_service
        )

    def get_prices(
        self,
        instruments: tuple[
            ValuationInstrument,
            ...
        ],
    ) -> dict[
        tuple[
            Market,
            str,
        ],
        ValuationPrice,
    ]:
        if not instruments:
            return {}

        instruments_by_symbol: dict[
            str,
            list[
                ValuationInstrument
            ],
        ] = {}

        for instrument in instruments:
            instruments_by_symbol.setdefault(
                instrument.symbol,
                [],
            ).append(
                instrument
            )

        requested_symbols: list[
            str
        ] = []

        for (
            symbol,
            symbol_instruments,
        ) in instruments_by_symbol.items():
            markets = {
                instrument.market
                for instrument
                in symbol_instruments
            }

            if len(markets) != 1:
                # The current market batch API is symbol-oriented.
                # Do not guess when the same symbol is present in
                # more than one market.
                continue

            requested_symbols.append(
                symbol
            )

        if not requested_symbols:
            return {}

        response = (
            self._batch_service
            .get_quotes(
                requested_symbols
            )
        )

        prices: dict[
            tuple[
                Market,
                str,
            ],
            ValuationPrice,
        ] = {}

        for item in response.items:
            if item.status not in {
                "ok",
                "stale",
            }:
                continue

            quote = item.quote

            if quote is None:
                continue

            normalized_symbol = (
                item.symbol
                .strip()
                .upper()
            )

            matching_instruments = (
                instruments_by_symbol
                .get(
                    normalized_symbol
                )
            )

            if not matching_instruments:
                continue

            markets = {
                instrument.market
                for instrument
                in matching_instruments
            }

            if len(markets) != 1:
                continue

            market = next(
                iter(markets)
            )

            if (
                quote.close
                <= Decimal("0")
            ):
                continue

            valuation_price = (
                ValuationPrice(
                    market=market,
                    symbol=(
                        normalized_symbol
                    ),
                    price=quote.close,
                    timestamp=(
                        quote.timestamp
                    ),
                    stale=(
                        item.status
                        == "stale"
                    ),
                )
            )

            prices[
                valuation_price.key
            ] = valuation_price

        return prices