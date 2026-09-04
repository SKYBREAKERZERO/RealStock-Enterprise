from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import IntegrityError

from libs.domain.portfolio import Portfolio
from services.api.dependencies import (
    get_current_user_id,
    get_portfolio_service,
)
from services.api.portfolio.service import (
    PortfolioNotFoundError,
    PortfolioService,
    PositionAlreadyExistsError,
)
from services.api.schemas.portfolio import (
    CreatePortfolioRequest,
    CreatePositionRequest,
    PortfolioResponse,
    PositionResponse,
)


router = APIRouter(
    prefix="/api/v1/portfolios",
    tags=["portfolios"],
)


CurrentUserId = Annotated[
    str,
    Depends(get_current_user_id),
]

PortfolioServiceDependency = Annotated[
    PortfolioService,
    Depends(get_portfolio_service),
]


def get_owned_portfolio(
    *,
    service: PortfolioService,
    portfolio_id: UUID,
    user_id: str,
) -> Portfolio:
    """
    Load a portfolio and enforce ownership.

    404 is deliberately returned for both:
    - resource does not exist
    - resource belongs to another user

    This avoids leaking resource existence.
    """

    try:
        portfolio = service.get_portfolio(
            portfolio_id=portfolio_id,
        )

    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="portfolio not found",
        ) from exc

    if portfolio.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="portfolio not found",
        )

    return portfolio


@router.post(
    "",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio(
    request: CreatePortfolioRequest,
    user_id: CurrentUserId,
    service: PortfolioServiceDependency,
) -> PortfolioResponse:
    portfolio = service.create_portfolio(
        user_id=user_id,
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
    user_id: CurrentUserId,
    service: PortfolioServiceDependency,
) -> list[PortfolioResponse]:
    portfolios = service.list_portfolios(
        user_id=user_id,
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
    user_id: CurrentUserId,
    service: PortfolioServiceDependency,
) -> PortfolioResponse:
    portfolio = get_owned_portfolio(
        service=service,
        portfolio_id=portfolio_id,
        user_id=user_id,
    )

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
    request: CreatePositionRequest,
    user_id: CurrentUserId,
    service: PortfolioServiceDependency,
) -> PositionResponse:
    get_owned_portfolio(
        service=service,
        portfolio_id=portfolio_id,
        user_id=user_id,
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
            detail="portfolio not found",
        ) from exc

    except PositionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="position already exists",
        ) from exc

    except IntegrityError as exc:
        # Protect against concurrent duplicate inserts.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="position already exists",
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
    user_id: CurrentUserId,
    service: PortfolioServiceDependency,
) -> list[PositionResponse]:
    get_owned_portfolio(
        service=service,
        portfolio_id=portfolio_id,
        user_id=user_id,
    )

    try:
        positions = service.list_positions(
            portfolio_id=portfolio_id,
        )

    except PortfolioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="portfolio not found",
        ) from exc

    return [
        PositionResponse.from_domain(
            position
        )
        for position in positions
    ]