from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from libs.database.engine import get_engine


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """
    Return one cached SQLAlchemy session factory.
    """

    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db_session() -> Generator[Session, None, None]:
    """
    Yield one database session.

    Intended for FastAPI dependency injection.
    """

    session_factory = get_session_factory()

    with session_factory() as session:
        yield session