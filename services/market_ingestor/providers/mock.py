from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import count

from libs.domain.market import (
    Market,
    MarketQuote,
    MarketTrade,
    TradeSide,
)

PRICE_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class MockInstrument:
    """
    Configuration for one mock market instrument.
    """

    symbol: str
    market: Market
    base_price: Decimal

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        if self.base_price <= Decimal("0"):
            raise ValueError(
                "base_price must be greater than zero"
            )

        object.__setattr__(
            self,
            "symbol",
            symbol,
        )


DEFAULT_INSTRUMENTS: tuple[
    MockInstrument,
    ...
] = (
    MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    ),
    MockInstrument(
        symbol="MSFT",
        market=Market.US,
        base_price=Decimal("417.30"),
    ),
    MockInstrument(
        symbol="NVDA",
        market=Market.US,
        base_price=Decimal("128.40"),
    ),
    MockInstrument(
        symbol="7203",
        market=Market.JP,
        base_price=Decimal("2865.00"),
    ),
    MockInstrument(
        symbol="6758",
        market=Market.JP,
        base_price=Decimal("13820.00"),
    ),
)


class MockMarketDataProvider:
    """
    Deterministic mock market data generator.

    When a seed is provided, the generated sequence is repeatable.
    This makes the provider suitable for local development,
    demonstrations and automated tests.
    """

    def __init__(
        self,
        *,
        instruments: Sequence[
            MockInstrument
        ] | None = None,
        seed: int | None = None,
    ) -> None:
        selected_instruments = (
            tuple(instruments)
            if instruments is not None
            else DEFAULT_INSTRUMENTS
        )

        if not selected_instruments:
            raise ValueError(
                "at least one instrument is required"
            )

        self._instruments = (
            selected_instruments
        )

        self._random = random.Random(
            seed
        )

        self._trade_sequence = count(
            start=1
        )

    @property
    def instruments(
        self,
    ) -> tuple[MockInstrument, ...]:
        return self._instruments

    def _select_instrument(
        self,
    ) -> MockInstrument:
        return self._random.choice(
            self._instruments
        )

    def _price_delta(
        self,
        *,
        base_price: Decimal,
    ) -> Decimal:
        """
        Generate a small price movement around the base price.

        The simulated movement is approximately +/- 0.5%.
        """

        basis_points = self._random.randint(
            -50,
            50,
        )

        ratio = (
            Decimal(basis_points)
            / Decimal("10000")
        )

        return (
            base_price
            * ratio
        )

    @staticmethod
    def _normalize_price(
        value: Decimal,
    ) -> Decimal:
        return value.quantize(
            PRICE_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

    def generate_trade(
        self,
        *,
        instrument: MockInstrument | None = None,
        timestamp: datetime | None = None,
    ) -> MarketTrade:
        selected = (
            instrument
            if instrument is not None
            else self._select_instrument()
        )

        occurred_at = (
            timestamp
            if timestamp is not None
            else datetime.now(
                UTC
            )
        )

        price = self._normalize_price(
            selected.base_price
            + self._price_delta(
                base_price=selected.base_price,
            )
        )

        # Defensive lower bound. Under current movement limits this
        # should never trigger, but protects the domain invariant.
        if price <= Decimal("0"):
            price = PRICE_QUANTUM

        quantity = self._random.randint(
            1,
            1000,
        )

        side = self._random.choice(
            (
                TradeSide.BUY,
                TradeSide.SELL,
            )
        )

        sequence = next(
            self._trade_sequence
        )

        trade_id = (
            f"mock-"
            f"{selected.market.value.lower()}-"
            f"{selected.symbol.lower()}-"
            f"{sequence:010d}"
        )

        return MarketTrade(
            trade_id=trade_id,
            symbol=selected.symbol,
            market=selected.market,
            price=price,
            quantity=quantity,
            side=side,
            timestamp=occurred_at,
        )

    def generate_quote(
        self,
        *,
        instrument: MockInstrument | None = None,
        timestamp: datetime | None = None,
    ) -> MarketQuote:
        selected = (
            instrument
            if instrument is not None
            else self._select_instrument()
        )

        occurred_at = (
            timestamp
            if timestamp is not None
            else datetime.now(
                UTC
            )
        )

        mid_price = self._normalize_price(
            selected.base_price
            + self._price_delta(
                base_price=selected.base_price,
            )
        )

        if mid_price <= Decimal("0"):
            mid_price = PRICE_QUANTUM

        # Spread: 1–10 cents for the local simulator.
        half_spread = (
            Decimal(
                self._random.randint(
                    1,
                    10,
                )
            )
            / Decimal("200")
        )

        bid_price = self._normalize_price(
            mid_price
            - half_spread
        )

        ask_price = self._normalize_price(
            mid_price
            + half_spread
        )

        if bid_price <= Decimal("0"):
            bid_price = PRICE_QUANTUM

        if ask_price < bid_price:
            ask_price = bid_price

        bid_size = self._random.randint(
            1,
            5000,
        )

        ask_size = self._random.randint(
            1,
            5000,
        )

        return MarketQuote(
            symbol=selected.symbol,
            market=selected.market,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            timestamp=occurred_at,
        )