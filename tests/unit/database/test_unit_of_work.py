from __future__ import annotations

from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from libs.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
    UnitOfWork,
)

pytestmark = pytest.mark.unit


def _session() -> Mock:
    """
    Return a Session-shaped mock for Unit of Work tests.
    """

    return Mock(
        spec=Session
    )


def _accept_unit_of_work(
    unit_of_work: UnitOfWork,
) -> UnitOfWork:
    """
    Static typing helper.

    SqlAlchemyUnitOfWork satisfies UnitOfWork through
    structural typing.
    """

    return unit_of_work


def test_sqlalchemy_unit_of_work_satisfies_protocol() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    result = _accept_unit_of_work(
        uow
    )

    assert result is uow


def test_unit_of_work_repository_uses_shared_session() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    assert uow.portfolios._session is session


def test_explicit_commit_commits_once() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    with uow:
        uow.commit()

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_uncommitted_work_rolls_back_on_exit() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    with uow:
        pass

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_exception_rolls_back_and_propagates() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        with uow:
            raise RuntimeError(
                "boom"
            )

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_commit_failure_rolls_back() -> None:
    session = _session()

    session.commit.side_effect = RuntimeError(
        "commit failed"
    )

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    with pytest.raises(
        RuntimeError,
        match="commit failed",
    ):
        with uow:
            uow.commit()

    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()


def test_explicit_rollback_is_not_repeated_on_exit() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    with uow:
        uow.rollback()

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_unit_of_work_does_not_close_session() -> None:
    session = _session()

    uow = SqlAlchemyUnitOfWork(
        session,
    )

    with uow:
        pass

    session.close.assert_not_called()