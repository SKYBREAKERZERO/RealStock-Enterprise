from __future__ import annotations

import time
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import delete

from libs.aws import get_kinesis_client
from libs.cache import (
    MarketQuoteCache,
    get_redis_client,
)
from libs.database import get_session_factory
from libs.database.models import (
    PortfolioModel,
    PositionModel,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from services.api.main import app
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
)
from services.market_ingestor.service import (
    MarketIngestorService,
)

pytestmark = pytest.mark.integration


STREAM_NAME = "realstock-market-events-local"

STREAM_WAIT_RETRY_COUNT = 40
STREAM_WAIT_INTERVAL_SECONDS = 0.25

USER_HEADERS = {
    "X-User-Id": "e2e-user-001",
}


client = TestClient(app)


def ensure_stream_exists() -> None:
    """
    Ensure the LocalStack Kinesis stream exists and is ACTIVE.
    """

    kinesis = get_kinesis_client()

    try:
        response = kinesis.describe_stream_summary(
            StreamName=STREAM_NAME,
        )

        status = response[
            "StreamDescriptionSummary"
        ]["StreamStatus"]

        if status == "ACTIVE":
            return

    except ClientError as exc:
        error_code = (
            exc.response
            .get("Error", {})
            .get("Code")
        )

        if error_code != "ResourceNotFoundException":
            raise

        kinesis.create_stream(
            StreamName=STREAM_NAME,
            ShardCount=1,
        )

    for _ in range(
        STREAM_WAIT_RETRY_COUNT
    ):
        try:
            response = (
                kinesis.describe_stream_summary(
                    StreamName=STREAM_NAME,
                )
            )

            status = response[
                "StreamDescriptionSummary"
            ]["StreamStatus"]

            if status == "ACTIVE":
                return

        except ClientError:
            pass

        time.sleep(
            STREAM_WAIT_INTERVAL_SECONDS
        )

    raise RuntimeError(
        "Kinesis stream did not become ACTIVE: "
        f"{STREAM_NAME}"
    )


@pytest.fixture(autouse=True)
def cleanup_environment():
    """
    Keep PostgreSQL and Redis deterministic for the E2E test.
    """

    session_factory = get_session_factory()

    with session_factory() as session:
        session.execute(
            delete(PositionModel)
        )
        session.execute(
            delete(PortfolioModel)
        )
        session.commit()

    redis_client = get_redis_client()

    for key in redis_client.scan_iter(
        match="realstock:quote:*"
    ):
        redis_client.delete(key)

    yield

    with session_factory() as session:
        session.execute(
            delete(PositionModel)
        )
        session.execute(
            delete(PortfolioModel)
        )
        session.commit()

    for key in redis_client.scan_iter(
        match="realstock:quote:*"
    ):
        redis_client.delete(key)


def build_quote() -> MarketQuote:
    return MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=Decimal("210.00"),
        ask_price=Decimal("212.00"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            5,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def test_market_quote_updates_portfolio_valuation() -> None:
    """
    Complete RealStock business E2E:

        Portfolio API
            ↓
        PostgreSQL

        MarketQuote
            ↓
        MarketIngestorService
            ↓
        LocalStack Kinesis
            ↓
        Redis latest-quote read model

        Portfolio Valuation API
            ↓
        Real-time market value / PnL
    """

    # --------------------------------------------------------
    # Infrastructure
    # --------------------------------------------------------

    ensure_stream_exists()

    # --------------------------------------------------------
    # 1. Create portfolio
    # --------------------------------------------------------

    portfolio_response = client.post(
        "/api/v1/portfolios",
        headers=USER_HEADERS,
        json={
            "name": "E2E Growth Portfolio",
            "currency": "USD",
        },
    )

    assert (
        portfolio_response.status_code
        == 201
    )

    portfolio = (
        portfolio_response.json()
    )

    portfolio_id = portfolio[
        "portfolio_id"
    ]

    # --------------------------------------------------------
    # 2. Add AAPL position
    #
    # quantity     = 100
    # average cost = 200.50
    # cost basis   = 20,050
    # --------------------------------------------------------

    position_response = client.post(
        (
            "/api/v1/portfolios/"
            f"{portfolio_id}"
            "/positions"
        ),
        headers=USER_HEADERS,
        json={
            "symbol": "AAPL",
            "market": "US",
            "quantity": "100",
            "average_cost": "200.50",
        },
    )

    assert (
        position_response.status_code
        == 201
    )

    # --------------------------------------------------------
    # 3. Before quote:
    #    valuation must be incomplete
    # --------------------------------------------------------

    before_response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio_id}"
            "/valuation"
        ),
        headers=USER_HEADERS,
    )

    assert (
        before_response.status_code
        == 200
    )

    before = before_response.json()

    assert (
        Decimal(
            before["total_cost_basis"]
        )
        == Decimal("20050.00")
    )

    assert (
        before["priced_positions"]
        == 0
    )

    assert (
        before["missing_quotes"]
        == 1
    )

    assert (
        before["valuation_complete"]
        is False
    )

    before_position = (
        before["positions"][0]
    )

    assert (
        before_position["quote_available"]
        is False
    )

    assert (
        before_position["market_price"]
        is None
    )

    assert (
        before_position["market_value"]
        is None
    )

    # --------------------------------------------------------
    # 4. Market quote enters the system
    #
    # bid = 210
    # ask = 212
    # mid = 211
    # --------------------------------------------------------

    producer = KinesisMarketEventProducer(
        stream_name=STREAM_NAME,
    )

    quote_cache = MarketQuoteCache(
        ttl_seconds=30,
    )

    market_ingestor = (
        MarketIngestorService(
            producer=producer,
            quote_cache=quote_cache,
        )
    )

    publish_result = (
        market_ingestor.ingest_quote(
            build_quote()
        )
    )

    # --------------------------------------------------------
    # 5. Verify Kinesis publication succeeded
    # --------------------------------------------------------

    assert publish_result.shard_id

    assert (
        publish_result.sequence_number
    )

    # --------------------------------------------------------
    # 6. Verify Redis latest-quote read model
    # --------------------------------------------------------

    cached_quote = (
        quote_cache.get_quote(
            market=Market.US,
            symbol="AAPL",
        )
    )

    assert cached_quote is not None

    assert (
        cached_quote.symbol
        == "AAPL"
    )

    assert (
        cached_quote.market
        == Market.US
    )

    assert (
        cached_quote.mid_price
        == Decimal("211.00")
    )

    # --------------------------------------------------------
    # 7. Query valuation again
    # --------------------------------------------------------

    after_response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio_id}"
            "/valuation"
        ),
        headers=USER_HEADERS,
    )

    assert (
        after_response.status_code
        == 200
    )

    after = after_response.json()

    # --------------------------------------------------------
    # Portfolio calculation
    #
    # Cost basis:
    #   100 × 200.50 = 20,050
    #
    # Market value:
    #   100 × 211 = 21,100
    #
    # Unrealized PnL:
    #   21,100 - 20,050 = 1,050
    # --------------------------------------------------------

    assert (
        Decimal(
            after["total_cost_basis"]
        )
        == Decimal("20050.00")
    )

    assert (
        Decimal(
            after["priced_cost_basis"]
        )
        == Decimal("20050.00")
    )

    assert (
        Decimal(
            after["total_market_value"]
        )
        == Decimal("21100.00")
    )

    assert (
        Decimal(
            after[
                "total_unrealized_pnl"
            ]
        )
        == Decimal("1050.00")
    )

    assert (
        after["priced_positions"]
        == 1
    )

    assert (
        after["missing_quotes"]
        == 0
    )

    assert (
        after["valuation_complete"]
        is True
    )

    # --------------------------------------------------------
    # Position calculation
    # --------------------------------------------------------

    position = after[
        "positions"
    ][0]

    assert (
        position["symbol"]
        == "AAPL"
    )

    assert (
        position["market"]
        == "US"
    )

    assert (
        Decimal(
            position["cost_basis"]
        )
        == Decimal("20050.00")
    )

    assert (
        Decimal(
            position["market_price"]
        )
        == Decimal("211.00")
    )

    assert (
        Decimal(
            position["market_value"]
        )
        == Decimal("21100.00")
    )

    assert (
        Decimal(
            position[
                "unrealized_pnl"
            ]
        )
        == Decimal("1050.00")
    )

    assert (
        position["quote_available"]
        is True
    )

    assert (
        position["quote_timestamp"]
        is not None
    )
