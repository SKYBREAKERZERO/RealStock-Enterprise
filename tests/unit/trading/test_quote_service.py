from decimal import Decimal

import pytest

from libs.trading.market import MarketQuote
from services.trading.quote_service import (
    QuoteService,
    RawQuote,
    StaticQuoteProvider,
)


def test_quote_service_returns_normalized_quote() -> None:
    provider = StaticQuoteProvider(
        {
            "AAPL": RawQuote(
                symbol="AAPL",
                bid=Decimal("229.44"),
                ask=Decimal("229.46"),
            ),
        }
    )

    service = QuoteService(
        provider=provider,
    )

    quote = service.get_quote("aapl")

    assert quote == MarketQuote(
        symbol="AAPL",
        bid=Decimal("229.44"),
        ask=Decimal("229.46"),
    )


def test_quote_service_normalizes_symbol() -> None:
    provider = StaticQuoteProvider(
        {
            "AAPL": RawQuote(
                symbol="AAPL",
                bid=Decimal("100"),
                ask=Decimal("100.10"),
            ),
        }
    )

    service = QuoteService(
        provider=provider,
    )

    quote = service.get_quote("  aapl  ")

    assert quote.symbol == "AAPL"


def test_quote_service_rejects_empty_symbol() -> None:
    provider = StaticQuoteProvider({})

    service = QuoteService(
        provider=provider,
    )

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        service.get_quote("   ")


def test_quote_service_rejects_missing_quote() -> None:
    provider = StaticQuoteProvider({})

    service = QuoteService(
        provider=provider,
    )

    with pytest.raises(
        ValueError,
        match="No market quote available for AAPL",
    ):
        service.get_quote("AAPL")


def test_quote_service_rejects_wrong_provider_symbol() -> None:
    class WrongSymbolProvider:
        def get_quote(
            self,
            symbol: str,
        ) -> MarketQuote:
            return MarketQuote(
                symbol="MSFT",
                bid=Decimal("400"),
                ask=Decimal("400.10"),
            )

    service = QuoteService(
        provider=WrongSymbolProvider(),
    )

    with pytest.raises(
        ValueError,
        match="unexpected symbol",
    ):
        service.get_quote("AAPL")