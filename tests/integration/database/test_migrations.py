from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from libs.database.engine import get_engine
from libs.database.models import Base

pytestmark = pytest.mark.integration


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = PROJECT_ROOT / "database" / "alembic.ini"
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"


def _repository_head() -> str:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option(
        "script_location",
        str(MIGRATIONS_DIR),
    )

    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()

    assert head is not None
    return head


def test_database_revision_matches_repository_head() -> None:
    engine = get_engine()

    with engine.connect() as connection:
        database_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert database_revision == _repository_head()


def test_baseline_tables_exist() -> None:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())

    assert "alembic_version" in tables
    assert "portfolios" in tables
    assert "positions" in tables


def test_positions_foreign_key_targets_portfolios() -> None:
    inspector = inspect(get_engine())
    foreign_keys = inspector.get_foreign_keys("positions")

    matching_foreign_keys = [
        foreign_key
        for foreign_key in foreign_keys
        if (
            foreign_key["constrained_columns"] == ["portfolio_id"]
            and foreign_key["referred_table"] == "portfolios"
            and foreign_key["referred_columns"] == ["id"]
        )
    ]

    assert len(matching_foreign_keys) == 1
    assert (
        matching_foreign_keys[0]
        .get("options", {})
        .get("ondelete")
        == "CASCADE"
    )


def test_portfolio_and_position_indexes_exist() -> None:
    inspector = inspect(get_engine())

    portfolio_indexes = {
        index["name"]
        for index in inspector.get_indexes("portfolios")
    }
    position_indexes = {
        index["name"]
        for index in inspector.get_indexes("positions")
    }

    assert "ix_portfolios_user_id" in portfolio_indexes
    assert "ix_positions_portfolio_id" in position_indexes


def test_position_business_key_is_unique() -> None:
    inspector = inspect(get_engine())

    constraints = {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints("positions")
    }

    assert constraints[
        "uq_positions_portfolio_market_symbol"
    ] == [
        "portfolio_id",
        "market",
        "symbol",
    ]


def test_database_schema_matches_sqlalchemy_metadata() -> None:
    engine = get_engine()

    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)

        differences = compare_metadata(
            migration_context,
            Base.metadata,
        )

    assert differences == []