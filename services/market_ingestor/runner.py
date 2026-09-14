from __future__ import annotations

import argparse
import logging
import signal
from dataclasses import dataclass
from threading import Event
from typing import Literal

from libs.domain.market import (
    MarketQuote,
    MarketTrade,
)
from libs.events.envelope import EventEnvelope
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
)
from services.market_ingestor.providers.mock import (
    MockMarketDataProvider,
)

# ============================================================
# Constants
# ============================================================

DEFAULT_STREAM_NAME = "realstock-market-events-local"

DEFAULT_INTERVAL_SECONDS = 1.0

DEFAULT_MODE = "both"

LOGGER_NAME = "realstock.market_ingestor"


# ============================================================
# Logging
# ============================================================


logger = logging.getLogger(
    LOGGER_NAME
)


def configure_logging(
    *,
    log_level: str,
) -> None:
    level = getattr(
        logging,
        log_level.upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )


# ============================================================
# Runner configuration
# ============================================================


RunnerMode = Literal[
    "trade",
    "quote",
    "both",
]


@dataclass(
    frozen=True,
    slots=True,
)
class RunnerConfig:
    stream_name: str
    mode: RunnerMode
    interval_seconds: float
    max_events: int | None
    seed: int | None

    def __post_init__(self) -> None:
        if not self.stream_name.strip():
            raise ValueError(
                "stream_name must not be empty"
            )

        if self.interval_seconds < 0:
            raise ValueError(
                "interval_seconds must be >= 0"
            )

        if (
            self.max_events is not None
            and self.max_events <= 0
        ):
            raise ValueError(
                "max_events must be greater than zero"
            )


# ============================================================
# Market event factory
# ============================================================


def create_trade_event(
    trade: MarketTrade,
) -> EventEnvelope[dict[str, object]]:
    """
    Convert a MarketTrade domain object into the standard
    RealStock event envelope.
    """

    return EventEnvelope[
        dict[str, object]
    ](
        event_type="market.trade.received",
        schema_version=1,
        source="market-ingestor",
        occurred_at=trade.timestamp,
        payload={
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "market": trade.market.value,
            "price": str(
                trade.price
            ),
            "quantity": trade.quantity,
            "side": trade.side.value,
        },
    )


def create_quote_event(
    quote: MarketQuote,
) -> EventEnvelope[dict[str, object]]:
    """
    Convert a MarketQuote domain object into the standard
    RealStock event envelope.
    """

    return EventEnvelope[
        dict[str, object]
    ](
        event_type="market.quote.received",
        schema_version=1,
        source="market-ingestor",
        occurred_at=quote.timestamp,
        payload={
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
            "mid_price": str(
                quote.mid_price
            ),
            "spread": str(
                quote.spread
            ),
        },
    )


# ============================================================
# Market ingestor runner
# ============================================================


class MarketIngestorRunner:
    """
    Long-running local Market Ingestor process.

    Responsibilities:

        Mock Provider
            ↓
        Domain Model
            ↓
        EventEnvelope
            ↓
        Kinesis Producer

    The runner controls process lifecycle only.
    """

    def __init__(
        self,
        *,
        config: RunnerConfig,
        provider: MockMarketDataProvider,
        producer: KinesisMarketEventProducer,
    ) -> None:
        self._config = config
        self._provider = provider
        self._producer = producer

        self._stop_event = Event()

        self._published_count = 0

        # Used when mode="both".
        self._publish_trade_next = True

    @property
    def published_count(
        self,
    ) -> int:
        return self._published_count

    def stop(self) -> None:
        """
        Request graceful shutdown.
        """

        logger.info(
            "shutdown_requested"
        )

        self._stop_event.set()

    def _should_stop(self) -> bool:
        if self._stop_event.is_set():
            return True

        max_events = (
            self._config.max_events
        )

        if max_events is None:
            return False

        return (
            self._published_count
            >= max_events
        )

    def _next_event_type(
        self,
    ) -> Literal[
        "trade",
        "quote",
    ]:
        mode = self._config.mode

        if mode == "trade":
            return "trade"

        if mode == "quote":
            return "quote"

        # mode == "both"
        if self._publish_trade_next:
            self._publish_trade_next = False
            return "trade"

        self._publish_trade_next = True

        return "quote"

    def _publish_trade(
        self,
    ) -> None:
        trade = (
            self._provider
            .generate_trade()
        )

        event = create_trade_event(
            trade
        )

        result = (
            self._producer.publish(
                event=event,
                partition_key=trade.symbol,
            )
        )

        self._published_count += 1

        logger.info(
            "market_trade_published "
            "event_id=%s "
            "trade_id=%s "
            "symbol=%s "
            "market=%s "
            "price=%s "
            "quantity=%s "
            "side=%s "
            "shard_id=%s "
            "sequence_number=%s",
            event.event_id,
            trade.trade_id,
            trade.symbol,
            trade.market.value,
            trade.price,
            trade.quantity,
            trade.side.value,
            result.shard_id,
            result.sequence_number,
        )

    def _publish_quote(
        self,
    ) -> None:
        quote = (
            self._provider
            .generate_quote()
        )

        event = create_quote_event(
            quote
        )

        result = (
            self._producer.publish(
                event=event,
                partition_key=quote.symbol,
            )
        )

        self._published_count += 1

        logger.info(
            "market_quote_published "
            "event_id=%s "
            "symbol=%s "
            "market=%s "
            "bid=%s "
            "ask=%s "
            "spread=%s "
            "shard_id=%s "
            "sequence_number=%s",
            event.event_id,
            quote.symbol,
            quote.market.value,
            quote.bid_price,
            quote.ask_price,
            quote.spread,
            result.shard_id,
            result.sequence_number,
        )

    def publish_once(
        self,
    ) -> None:
        event_type = (
            self._next_event_type()
        )

        if event_type == "trade":
            self._publish_trade()
            return

        self._publish_quote()

    def run(self) -> None:
        logger.info(
            "market_ingestor_started "
            "stream=%s "
            "mode=%s "
            "interval_seconds=%s "
            "max_events=%s",
            self._config.stream_name,
            self._config.mode,
            self._config.interval_seconds,
            self._config.max_events,
        )

        try:
            while not self._should_stop():
                self.publish_once()

                if self._should_stop():
                    break

                if (
                    self._config
                    .interval_seconds
                    > 0
                ):
                    self._stop_event.wait(
                        self._config
                        .interval_seconds
                    )

        except KeyboardInterrupt:
            logger.info(
                "keyboard_interrupt_received"
            )

        finally:
            logger.info(
                "market_ingestor_stopped "
                "published_count=%s",
                self._published_count,
            )


# ============================================================
# CLI
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="realstock-market-ingestor",
        description=(
            "RealStock Enterprise local "
            "market event generator"
        ),
    )

    parser.add_argument(
        "--stream-name",
        default=DEFAULT_STREAM_NAME,
        help=(
            "Kinesis stream name "
            f"(default: {DEFAULT_STREAM_NAME})"
        ),
    )

    parser.add_argument(
        "--mode",
        choices=(
            "trade",
            "quote",
            "both",
        ),
        default=DEFAULT_MODE,
        help=(
            "Event generation mode "
            "(default: both)"
        ),
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=(
            "Seconds between events "
            "(default: 1.0)"
        ),
    )

    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help=(
            "Stop after publishing this "
            "number of events. "
            "Default is unlimited."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Optional deterministic "
            "mock random seed"
        ),
    )

    parser.add_argument(
        "--log-level",
        choices=(
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
        ),
        default="INFO",
    )

    return parser


# ============================================================
# Process bootstrap
# ============================================================


def install_signal_handlers(
    runner: MarketIngestorRunner,
) -> None:
    """
    Install graceful shutdown handlers where supported.
    """

    def handle_signal(
        signum: int,
        _frame: object,
    ) -> None:
        logger.info(
            "signal_received signal=%s",
            signum,
        )

        runner.stop()

    signal.signal(
        signal.SIGINT,
        handle_signal,
    )

    if hasattr(
        signal,
        "SIGTERM",
    ):
        signal.signal(
            signal.SIGTERM,
            handle_signal,
        )


def main() -> int:
    parser = build_parser()

    args = parser.parse_args()

    configure_logging(
        log_level=args.log_level,
    )

    try:
        config = RunnerConfig(
            stream_name=args.stream_name,
            mode=args.mode,
            interval_seconds=args.interval,
            max_events=args.count,
            seed=args.seed,
        )

        provider = (
            MockMarketDataProvider(
                seed=config.seed,
            )
        )

        producer = (
            KinesisMarketEventProducer(
                stream_name=(
                    config.stream_name
                ),
            )
        )

        runner = MarketIngestorRunner(
            config=config,
            provider=provider,
            producer=producer,
        )

        install_signal_handlers(
            runner
        )

        runner.run()

        return 0

    except Exception:
        logger.exception(
            "market_ingestor_failed"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )