from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from libs.database import get_db_session
from services.api.portfolio import (
    PortfolioNotFoundError,
    PortfolioService,
    PositionAlreadyExistsError,
)
from services.api.schemas import (
    PortfolioCreateRequest,
    PortfolioResponse,
    PositionCreateRequest,
    PositionResponse,
)


router = APIRouter(
    prefix="/api/v1/portfolios",
    tags=["portfolios"],
)


DbSession = Annotated[
    Session,
    Depends(get_db_session),
]


@router.post(
    "",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio(
    request: PortfolioCreateRequest,
    session: DbSession,
) -> PortfolioResponse:
    service = PortfolioService(
        session
    )

    portfolio = service.create_portfolio(
        user_id=request.user_id,
        name=request.name,
        currency=request.currency,
    )

    return PortfolioResponse.from_domain(
        portfolio
    )


@router.get(
    "",
    response_model=list[PortfolioResponse],
)
def list_portfolios(
    session: DbSession,
    user_id: Annotated[
        str,
        Query(
            min_length=1,
            max_length=128,
        ),
    ],
) -> list[PortfolioResponse]:
    service = PortfolioService(
        session
    )

    portfolios = service.list_portfolios(
        user_id=user_id
    )

    return [
        PortfolioResponse.from_domain(
            portfolio
        )
        for portfolio in portfolios
    ]


@router.get(
    "/{portfolio_id}",
    response_model=PortfolioResponse,
)
def get_portfolio(
    portfolio_id: UUID,
    session: DbSession,
) -> PortfolioResponse:
    service = PortfolioService(
        session
    )

    try:
        portfolio = service.get_portfolio(
            portfolio_id=portfolio_id
        )

    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PortfolioResponse.from_domain(
        portfolio
    )


@router.post(
    "/{portfolio_id}/positions",
    response_model=PositionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_position(
    portfolio_id: UUID,
    request: PositionCreateRequest,
    session: DbSession,
) -> PositionResponse:
    service = PortfolioService(
        session
    )

    try:
        position = service.add_position(
            portfolio_id=portfolio_id,
            symbol=request.symbol,
            market=request.market,
            quantity=request.quantity,
            average_cost=request.average_cost,
        )

    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PositionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PositionResponse.from_domain(
        position
    )


@router.get(
    "/{portfolio_id}/positions",
    response_model=list[PositionResponse],
)
def list_positions(
    portfolio_id: UUID,
    session: DbSession,
) -> list[PositionResponse]:
    service = PortfolioService(
        session
    )

    try:
        positions = service.list_positions(
            portfolio_id=portfolio_id
        )

    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [
        PositionResponse.from_domain(
            position
        )
        for position in positions
    ]