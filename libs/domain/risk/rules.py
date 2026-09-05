from __future__ import annotations

from decimal import Decimal

from libs.domain.market import MarketQuote
from libs.domain.risk.models import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)


class PriceMoveRule:
    """
    Detect significant percentage changes between two
    consecutive quotes for the same instrument.

    Example:

        previous mid = 100
        current mid  = 106

        change = +6%

    With:

        warning  = 2%
        critical = 5%

    the result is CRITICAL.
    """

    def __init__(
        self,
        *,
        warning_threshold_percent: Decimal = (
            Decimal("2")
        ),
        critical_threshold_percent: Decimal = (
            Decimal("5")
        ),
    ) -> None:
        if (
            warning_threshold_percent
            <= Decimal("0")
        ):
            raise ValueError(
                "warning threshold must be "
                "greater than zero"
            )

        if (
            critical_threshold_percent
            <= warning_threshold_percent
        ):
            raise ValueError(
                "critical threshold must be "
                "greater than warning threshold"
            )

        self._warning_threshold = (
            warning_threshold_percent
        )

        self._critical_threshold = (
            critical_threshold_percent
        )

    @property
    def warning_threshold_percent(
        self,
    ) -> Decimal:
        return self._warning_threshold

    @property
    def critical_threshold_percent(
        self,
    ) -> Decimal:
        return self._critical_threshold

    def evaluate(
        self,
        *,
        previous_quote: MarketQuote,
        current_quote: MarketQuote,
    ) -> RiskAlert | None:
        self._validate_instrument(
            previous_quote=previous_quote,
            current_quote=current_quote,
        )

        previous_price = (
            previous_quote.mid_price
        )

        current_price = (
            current_quote.mid_price
        )

        change_percent = (
            (
                current_price
                - previous_price
            )
            / previous_price
            * Decimal("100")
        )

        absolute_change = abs(
            change_percent
        )

        if (
            absolute_change
            < self._warning_threshold
        ):
            return None

        if (
            absolute_change
            >= self._critical_threshold
        ):
            severity = (
                RiskSeverity.CRITICAL
            )

            threshold = (
                self._critical_threshold
            )

        else:
            severity = (
                RiskSeverity.WARNING
            )

            threshold = (
                self._warning_threshold
            )

        return RiskAlert(
            risk_type=(
                RiskType.PRICE_MOVE_PERCENT
            ),
            severity=severity,
            market=current_quote.market,
            symbol=current_quote.symbol,
            observed_value=change_percent,
            threshold=threshold,
            message=(
                "Price move threshold exceeded "
                f"for "
                f"{current_quote.market.value}:"
                f"{current_quote.symbol}; "
                f"change={change_percent}%"
            ),
            occurred_at=(
                current_quote.timestamp
            ),
        )

    @staticmethod
    def _validate_instrument(
        *,
        previous_quote: MarketQuote,
        current_quote: MarketQuote,
    ) -> None:
        if (
            previous_quote.market
            != current_quote.market
            or previous_quote.symbol
            != current_quote.symbol
        ):
            raise ValueError(
                "quotes must belong to the "
                "same instrument"
            )