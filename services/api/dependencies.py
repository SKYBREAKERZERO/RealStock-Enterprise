from __future__ import annotations

from typing import Annotated

from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from libs.database import get_db_session
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from services.api.portfolio.service import (
    PortfolioService,
)
from services.api.portfolio.valuation import (
    PortfolioValuationService,
)


def get_current_user_id(
    x_user_id: Annotated[
        str | None,
        Header(alias="X-User-Id"),
    ] = None,
) -> str:
    """
    Temporary local identity boundary.

    Day N:
        X-User-Id

    Production:
        Cognito JWT -> sub
    """

    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-User-Id header",
        )

    user_id = x_user_id.strip()

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid X-User-Id header",
        )

    if len(user_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid X-User-Id header",
        )

    return user_id


def get_portfolio_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> PortfolioService:
    unit_of_work = SqlAlchemyUnitOfWork(
        session
    )

    return PortfolioService(
        unit_of_work
    )


def get_portfolio_valuation_service(
) -> PortfolioValuationService:
    return PortfolioValuationService()
