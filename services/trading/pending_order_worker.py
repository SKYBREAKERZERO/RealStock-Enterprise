from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from libs.cache import MarketQuoteCache
from libs.database.models import PaperOrderModel
from libs.database.session import get_session_factory
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from libs.trading.enums import OrderStatus, OrderType
from libs.trading.paper_broker import PaperBroker
from services.trading.alpaca_quote_provider import (
    AlpacaCachedTradingQuoteProvider,
)
from services.trading.cached_quote_provider import (
    CachedMarketQuoteProvider,
)
from services.trading.paper_trading_service import (
    PaperTradingService,
)
from services.trading.persistent_paper_trading_service import (
    PersistentPaperTradingService,
)
from services.trading.quote_service import QuoteService


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PendingOrderWorkerResult:
    discovered: int
    filled: int
    still_pending: int
    failed: int


class PendingOrderWorker:
    """
    Poll persisted PENDING LIMIT orders and process each order
    through the existing transactional trading service.

    Discovery is intentionally unlocked. The canonical concurrency
    boundary remains inside PersistentPaperTradingService:

        routing read
        -> account FOR UPDATE
        -> order FOR UPDATE
        -> position FOR UPDATE
        -> domain execution
        -> atomic commit

    Therefore this worker does not introduce a competing lock order.
    """

    def __init__(
        self,
        *,
        batch_size: int = 100,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero"
            )

        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than zero"
            )

        self._batch_size = batch_size
        self._poll_interval_seconds = (
            poll_interval_seconds
        )
        self._session_factory = (
            get_session_factory()
        )
        self._quote_provider = (
            self._build_quote_provider()
        )

    def run_once(
        self,
    ) -> PendingOrderWorkerResult:
        order_ids = self._discover_pending_order_ids()

        filled = 0
        still_pending = 0
        failed = 0

        for order_id in order_ids:
            try:
                execution = self._process_one(
                    order_id
                )
            except Exception:
                failed += 1
                logger.exception(
                    "pending_limit_order_failed "
                    "order_id=%s",
                    order_id,
                )
                continue

            if execution is None:
                still_pending += 1
                continue

            filled += 1

            logger.info(
                "pending_limit_order_filled "
                "order_id=%s execution_id=%s "
                "symbol=%s side=%s quantity=%s "
                "price=%s",
                order_id,
                execution.execution_id,
                execution.symbol,
                execution.side.value,
                execution.quantity,
                execution.price,
            )

        return PendingOrderWorkerResult(
            discovered=len(order_ids),
            filled=filled,
            still_pending=still_pending,
            failed=failed,
        )

    def run_forever(
        self,
    ) -> None:
        logger.info(
            "pending_order_worker_started "
            "batch_size=%s poll_interval_seconds=%s",
            self._batch_size,
            self._poll_interval_seconds,
        )

        while True:
            result = self.run_once()

            logger.info(
                "pending_order_worker_cycle "
                "discovered=%s filled=%s "
                "still_pending=%s failed=%s",
                result.discovered,
                result.filled,
                result.still_pending,
                result.failed,
            )

            time.sleep(
                self._poll_interval_seconds
            )

    def _discover_pending_order_ids(
        self,
    ) -> list[UUID]:
        with self._session_factory() as session:
            statement = (
                select(
                    PaperOrderModel.id
                )
                .where(
                    PaperOrderModel.order_type
                    == OrderType.LIMIT.value,
                    PaperOrderModel.status
                    == OrderStatus.PENDING.value,
                )
                .limit(
                    self._batch_size
                )
            )

            return list(
                session.scalars(
                    statement
                ).all()
            )

    def _process_one(
        self,
        order_id: UUID,
    ):
        with self._session_factory() as session:
            service = (
                PersistentPaperTradingService(
                    trading_service=(
                        PaperTradingService(
                            quote_service=(
                                QuoteService(
                                    provider=(
                                        self._quote_provider
                                    )
                                )
                            ),
                            broker=PaperBroker(),
                        )
                    ),
                    unit_of_work=(
                        SqlAlchemyUnitOfWork(
                            session
                        )
                    ),
                )
            )

            return service.process_limit_order(
                order_id=order_id
            )

    @staticmethod
    def _build_quote_provider():
        cache = MarketQuoteCache()

        key_id = os.getenv(
            "ALPACA_API_KEY_ID",
            "",
        ).strip()

        secret_key = os.getenv(
            "ALPACA_API_SECRET_KEY",
            "",
        ).strip()

        if bool(key_id) != bool(secret_key):
            raise RuntimeError(
                "ALPACA_API_KEY_ID and "
                "ALPACA_API_SECRET_KEY must be "
                "configured together."
            )

        if key_id and secret_key:
            return (
                AlpacaCachedTradingQuoteProvider(
                    cache=cache,
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
            )

        return CachedMarketQuoteProvider(
            cache=cache,
        )



def main() -> int:
    logging.basicConfig(
        level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ).upper(),
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        ),
    )

    worker = PendingOrderWorker(
        batch_size=int(
            os.getenv(
                "TRADING_ORDER_WORKER_BATCH_SIZE",
                "100",
            )
        ),
        poll_interval_seconds=float(
            os.getenv(
                "TRADING_ORDER_WORKER_POLL_SECONDS",
                "2",
            )
        ),
    )

    try:
        worker.run_forever()
    except KeyboardInterrupt:
        logger.info(
            "pending_order_worker_stopped"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
