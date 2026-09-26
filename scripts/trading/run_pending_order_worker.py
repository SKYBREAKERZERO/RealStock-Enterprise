from __future__ import annotations

import argparse
import logging
import os

from services.trading.pending_order_worker import (
    PendingOrderWorker,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Process persisted PENDING LIMIT paper orders."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(
            os.getenv(
                "TRADING_ORDER_WORKER_BATCH_SIZE",
                "100",
            )
        ),
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(
            os.getenv(
                "TRADING_ORDER_WORKER_POLL_SECONDS",
                "2",
            )
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

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
        batch_size=args.batch_size,
        poll_interval_seconds=(
            args.poll_interval
        ),
    )

    if args.once:
        result = worker.run_once()

        print(
            "PENDING ORDER WORKER "
            f"discovered={result.discovered} "
            f"filled={result.filled} "
            f"still_pending={result.still_pending} "
            f"failed={result.failed}"
        )

        return 0

    try:
        worker.run_forever()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info(
            "pending_order_worker_stopped"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
