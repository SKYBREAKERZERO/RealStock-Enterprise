from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal

from libs.cache import MarketQuoteCache
from libs.cache.market_quote_cache import MarketQuote
from libs.domain.market import Market


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed an explicit bid/ask quote into Redis "
            "for local paper-trading development."
        ),
    )

    parser.add_argument(
        "symbol",
        help="US stock symbol, e.g. AAPL",
    )
    parser.add_argument(
        "bid",
        type=Decimal,
        help="Explicit bid price",
    )
    parser.add_argument(
        "ask",
        type=Decimal,
        help="Explicit ask price",
    )
    parser.add_argument(
        "--bid-size",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--ask-size",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=300,
        help="Redis quote TTL in seconds (default: 300)",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    symbol = args.symbol.strip().upper()

    if not symbol:
        raise SystemExit(
            "symbol must not be empty"
        )

    if len(symbol) > 32:
        raise SystemExit(
            "symbol must not exceed 32 characters"
        )

    if args.bid <= 0 or args.ask <= 0:
        raise SystemExit(
            "bid and ask must be greater than zero"
        )

    if args.ask < args.bid:
        raise SystemExit(
            "ask must be greater than or equal to bid"
        )

    if args.bid_size < 0 or args.ask_size < 0:
        raise SystemExit(
            "bid-size and ask-size must not be negative"
        )

    if args.ttl <= 0:
        raise SystemExit(
            "ttl must be greater than zero"
        )

    cache = MarketQuoteCache(
        ttl_seconds=args.ttl,
    )

    quote = MarketQuote(
        symbol=symbol,
        market=Market.US,
        bid_price=args.bid,
        ask_price=args.ask,
        bid_size=args.bid_size,
        ask_size=args.ask_size,
        timestamp=datetime.now(
            UTC
        ),
    )

    cache.set_quote(
        quote
    )

    stored = cache.get_quote(
        market=Market.US,
        symbol=symbol,
    )

    if stored is None:
        raise RuntimeError(
            "quote was not persisted to Redis"
        )

    print(
        f"SEEDED {stored.market.value}:{stored.symbol} "
        f"bid={stored.bid_price} "
        f"ask={stored.ask_price} "
        f"bid_size={stored.bid_size} "
        f"ask_size={stored.ask_size} "
        f"ttl={args.ttl}s"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
