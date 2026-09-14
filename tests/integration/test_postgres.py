import pytest
from sqlalchemy import text

from libs.database import get_engine

pytestmark = pytest.mark.integration


def test_postgresql_connection() -> None:
    engine = get_engine()

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        ).scalar_one()

    assert result == 1