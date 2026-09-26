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

from libs.trading.exceptions import (
    InsufficientBuyingPowerError,
    InsufficientPositionError,
    InvalidOrderError,
)
from services.api.dependencies import (
    get_current_user_id,
    get_trading_portfolio_service,
    get_trading_query_service,
    get_trading_write_service,
)
from services.api.schemas.trading import (
    PaperAccountResponse,
    PaperExecutionResponse,
    PaperOrderResponse,
    PaperPositionResponse,
    TradingPortfolioResponse,
)
from services.api.schemas.trading_write import (
    LimitOrderProcessResponse,
    LimitOrderRequest,
    MarketOrderRequest,
    TradeExecutionResponse,
)
from services.trading.trading_portfolio_service import (
    TradingPortfolioAccountNotFoundError,
    TradingPortfolioService,
    TradingPortfolioValuationUnavailableError,
)
from services.trading.trading_query_service import (
    TradingQueryService,
)
from services.trading.trading_write_service import (
    TradingWriteAccountNotFoundError,
    TradingWriteOrderNotFoundError,
    TradingWriteService,
)


from services.api.dependencies import get_trading_account_service
from services.api.schemas.trading_write import CreatePaperAccountRequest
from services.trading.trading_account_service import (
    TradingAccountAlreadyExistsError,
    TradingAccountService,
)

router = APIRouter(
    prefix="/api/v1/trading",
    tags=["trading"],
)

CurrentUserId = Annotated[
    str,
    Depends(get_current_user_id),
]

TradingQueryServiceDependency = Annotated[
    TradingQueryService,
    Depends(get_trading_query_service),
]

TradingPortfolioServiceDependency = Annotated[
    TradingPortfolioService,
    Depends(get_trading_portfolio_service),
]

TradingAccountServiceDependency = Annotated[
    TradingAccountService,
    Depends(get_trading_account_service),
]

TradingWriteServiceDependency = Annotated[
    TradingWriteService,
    Depends(get_trading_write_service),
]

ReadLimit = Annotated[
    int,
    Query(
        ge=1,
        le=500,
    ),
]


def _paper_account_not_found(
    exc: Exception | None = None,
) -> HTTPException:
    exception = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="paper account not found",
    )

    if exc is not None:
        exception.__cause__ = exc

    return exception


def _paper_order_not_found(
    exc: Exception | None = None,
) -> HTTPException:
    exception = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="paper order not found",
    )

    if exc is not None:
        exception.__cause__ = exc

    return exception


def _raise_write_error(
    exc: Exception,
) -> None:
    if isinstance(
        exc,
        TradingWriteAccountNotFoundError,
    ):
        raise _paper_account_not_found(
            exc
        ) from exc

    if isinstance(
        exc,
        TradingWriteOrderNotFoundError,
    ):
        raise _paper_order_not_found(
            exc
        ) from exc

    if isinstance(
        exc,
        (
            InsufficientBuyingPowerError,
            InsufficientPositionError,
            InvalidOrderError,
        ),
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        ValueError,
    ):
        if (
            "No current bid/ask market quote "
            "available for "
            in str(exc)
        ):
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "current trading quote "
                    "is unavailable"
                ),
            ) from exc

        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(exc),
        ) from exc

    raise exc


@router.get(
    "/account",
    response_model=PaperAccountResponse,
)
def get_paper_account(
    user_id: CurrentUserId,
    service: TradingQueryServiceDependency,
) -> PaperAccountResponse:
    account = service.get_account(
        user_id=user_id,
    )

    if account is None:
        raise _paper_account_not_found()

    return PaperAccountResponse.from_domain(
        account
    )


@router.get(
    "/portfolio",
    response_model=TradingPortfolioResponse,
)
def get_paper_portfolio(
    user_id: CurrentUserId,
    service: TradingPortfolioServiceDependency,
) -> TradingPortfolioResponse:
    try:
        snapshot = service.get_snapshot(
            user_id=user_id,
        )

    except (
        TradingPortfolioAccountNotFoundError
    ) as exc:
        raise _paper_account_not_found(
            exc
        ) from exc

    except (
        TradingPortfolioValuationUnavailableError
    ) as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "paper portfolio valuation "
                "is unavailable"
            ),
        ) from exc

    return TradingPortfolioResponse.from_domain(
        snapshot
    )


@router.get(
    "/positions",
    response_model=list[PaperPositionResponse],
)
def list_paper_positions(
    user_id: CurrentUserId,
    service: TradingQueryServiceDependency,
) -> list[PaperPositionResponse]:
    try:
        positions = service.list_positions(
            user_id=user_id,
        )

    except ValueError as exc:
        raise _paper_account_not_found(
            exc
        ) from exc

    return [
        PaperPositionResponse.from_domain(
            position
        )
        for position in positions
    ]


@router.get(
    "/orders",
    response_model=list[PaperOrderResponse],
)
def list_paper_orders(
    user_id: CurrentUserId,
    service: TradingQueryServiceDependency,
    limit: ReadLimit = 100,
) -> list[PaperOrderResponse]:
    try:
        orders = service.list_orders(
            user_id=user_id,
            limit=limit,
        )

    except ValueError as exc:
        raise _paper_account_not_found(
            exc
        ) from exc

    return [
        PaperOrderResponse.from_domain(
            order
        )
        for order in orders
    ]


@router.get(
    "/orders/open",
    response_model=list[PaperOrderResponse],
)
def list_open_paper_orders(
    user_id: CurrentUserId,
    service: TradingQueryServiceDependency,
    limit: ReadLimit = 100,
) -> list[PaperOrderResponse]:
    try:
        orders = service.list_open_orders(
            user_id=user_id,
            limit=limit,
        )

    except ValueError as exc:
        raise _paper_account_not_found(
            exc
        ) from exc

    return [
        PaperOrderResponse.from_domain(
            order
        )
        for order in orders
    ]


@router.get(
    "/executions",
    response_model=list[PaperExecutionResponse],
)
def list_paper_executions(
    user_id: CurrentUserId,
    service: TradingQueryServiceDependency,
    limit: ReadLimit = 100,
) -> list[PaperExecutionResponse]:
    try:
        executions = service.list_executions(
            user_id=user_id,
            limit=limit,
        )

    except ValueError as exc:
        raise _paper_account_not_found(
            exc
        ) from exc

    return [
        PaperExecutionResponse.from_domain(
            execution
        )
        for execution in executions
    ]


@router.post(
    "/orders/market/buy",
    response_model=TradeExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def market_buy(
    request: MarketOrderRequest,
    user_id: CurrentUserId,
    service: TradingWriteServiceDependency,
) -> TradeExecutionResponse:
    try:
        result = service.market_buy(
            user_id=user_id,
            symbol=request.symbol,
            quantity=request.quantity,
        )

    except Exception as exc:
        _raise_write_error(
            exc
        )
        raise

    return TradeExecutionResponse.from_domain(
        result
    )


@router.post(
    "/orders/market/sell",
    response_model=TradeExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
def market_sell(
    request: MarketOrderRequest,
    user_id: CurrentUserId,
    service: TradingWriteServiceDependency,
) -> TradeExecutionResponse:
    try:
        result = service.market_sell(
            user_id=user_id,
            symbol=request.symbol,
            quantity=request.quantity,
        )

    except Exception as exc:
        _raise_write_error(
            exc
        )
        raise

    return TradeExecutionResponse.from_domain(
        result
    )


@router.post(
    "/orders/limit/buy",
    response_model=PaperOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_limit_buy(
    request: LimitOrderRequest,
    user_id: CurrentUserId,
    service: TradingWriteServiceDependency,
) -> PaperOrderResponse:
    try:
        order = service.submit_limit_buy(
            user_id=user_id,
            symbol=request.symbol,
            quantity=request.quantity,
            limit_price=request.limit_price,
        )

    except Exception as exc:
        _raise_write_error(
            exc
        )
        raise

    return PaperOrderResponse.from_domain(
        order
    )


@router.post(
    "/orders/limit/sell",
    response_model=PaperOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_limit_sell(
    request: LimitOrderRequest,
    user_id: CurrentUserId,
    service: TradingWriteServiceDependency,
) -> PaperOrderResponse:
    try:
        order = service.submit_limit_sell(
            user_id=user_id,
            symbol=request.symbol,
            quantity=request.quantity,
            limit_price=request.limit_price,
        )

    except Exception as exc:
        _raise_write_error(
            exc
        )
        raise

    return PaperOrderResponse.from_domain(
        order
    )


@router.post(
    "/orders/{order_id}/cancel",
    response_model=PaperOrderResponse,
)
def cancel_limit_order(
    order_id: UUID,
    user_id: CurrentUserId,
    service: TradingWriteServiceDependency,
) -> PaperOrderResponse:
    try:
        order = service.cancel_limit_order(
            user_id=user_id,
            order_id=order_id,
        )

    except Exception as exc:
        _raise_write_error(
            exc
        )
        raise

    return PaperOrderResponse.from_domain(
        order
    )


@router.post(
    "/orders/{order_id}/process",
    response_model=LimitOrderProcessResponse,
)
def process_limit_order(
    order_id: UUID,
    user_id: CurrentUserId,
    service: TradingWriteServiceDependency,
) -> LimitOrderProcessResponse:
    try:
        execution = service.process_limit_order(
            user_id=user_id,
            order_id=order_id,
        )

    except Exception as exc:
        _raise_write_error(
            exc
        )
        raise

    return LimitOrderProcessResponse(
        order_id=order_id,
        executed=execution is not None,
        execution=(
            PaperExecutionResponse.from_domain(
                execution
            )
            if execution is not None
            else None
        ),
    )

@router.post(
    "/account",
    response_model=PaperAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_paper_account(
    request: CreatePaperAccountRequest,
    user_id: CurrentUserId,
    service: TradingAccountServiceDependency,
) -> PaperAccountResponse:
    try:
        account = service.open_account(
            user_id=user_id,
            initial_cash=request.initial_cash,
        )
    except TradingAccountAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="paper account already exists",
        ) from exc

    return PaperAccountResponse.from_domain(account)

