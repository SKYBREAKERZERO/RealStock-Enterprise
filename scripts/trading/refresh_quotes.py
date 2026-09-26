from __future__ import annotations

import argparse
import os

from libs.cache import MarketQuoteCache
from services.trading.alpaca_quote_provider import (
    AlpacaCachedTradingQuoteProvider,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh real bid/ask quotes "
            "into MarketQuoteCache."
        )
    )

    parser.add_argument(
        "symbols",
        nargs="+",
        help="US stock symbols, e.g. AAPL MSFT",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    key_id = os.getenv(
        "ALPACA_API_KEY_ID",
        "",
    ).strip()

    secret_key = os.getenv(
        "ALPACA_API_SECRET_KEY",
        "",
    ).strip()

    if not key_id or not secret_key:
        raise SystemExit(
            "ALPACA_API_KEY_ID and "
            "ALPACA_API_SECRET_KEY are required."
        )

    provider = AlpacaCachedTradingQuoteProvider(
        cache=MarketQuoteCache(),
        api_key_id=key_id,
        api_secret_key=secret_key,
        feed=os.getenv(
            "ALPACA_DATA_FEED",
            "iex",
        ),
        base_url=os.getenv(
            "ALPACA_MARKET_DATA_BASE_URL",
            "https://data.alpaca.markets",
        ),
        timeout_seconds=float(
            os.getenv(
                "ALPACA_QUOTE_TIMEOUT_SECONDS",
                "5",
            )
        ),
    )

    for symbol in args.symbols:
        quote = provider.refresh_quote(
            symbol
        )

        print(
            f"{quote.symbol}: "
            f"bid={quote.bid} "
            f"ask={quote.ask}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
