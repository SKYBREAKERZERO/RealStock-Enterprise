from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.orm import Session

from libs.config import get_settings
from libs.database import get_session_factory
from services.api.schemas.watchlist import (
    AddWatchlistItemRequest,
    WatchlistItemResponse,
    WatchlistResponse,
)
from services.api.watchlist import (
    InvalidWatchlistSymbolError,
    WatchlistItemAlreadyExistsError,
    WatchlistItemNotFoundError,
    WatchlistLimitExceededError,
    WatchlistService,
)

router = APIRouter(
    prefix="/api/v1/watchlist",
    tags=["watchlist"],
)


def get_watchlist_session(
) -> Generator[
    Session,
    None,
    None,
]:
    session_factory = (
        get_session_factory()
    )

    session = (
        session_factory()
    )

    try:
        yield session

    finally:
        session.close()


def get_current_user_id(
    x_user_id: Annotated[
        str | None,
        Header(
            alias="X-User-ID"
        ),
    ] = None,
) -> str:
    if (
        x_user_id is None
        or not x_user_id.strip()
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "missing user identity"
            ),
        )

    normalized = (
        x_user_id.strip()
    )

    if len(normalized) > 128:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "user identity is too long"
            ),
        )

    return normalized


def get_watchlist_service(
    session: Annotated[
        Session,
        Depends(
            get_watchlist_session
        ),
    ],
) -> WatchlistService:
    settings = get_settings()

    return WatchlistService(
        session,
        max_items=(
            settings
            .market_batch_max_symbols
        ),
    )


def _to_response(
    model,
) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        watchlist_item_id=model.id,
        symbol=model.symbol,
        created_at=model.created_at,
    )


@router.get(
    "",
    response_model=WatchlistResponse,
)
def read_watchlist(
    user_id: Annotated[
        str,
        Depends(
            get_current_user_id
        ),
    ],
    service: Annotated[
        WatchlistService,
        Depends(
            get_watchlist_service
        ),
    ],
) -> WatchlistResponse:
    items = service.list_items(
        user_id=user_id,
    )

    response_items = [
        _to_response(
            item
        )
        for item in items
    ]

    return WatchlistResponse(
        items=response_items,
        count=len(
            response_items
        ),
    )


@router.post(
    "",
    response_model=WatchlistItemResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_watchlist_item(
    request: AddWatchlistItemRequest,
    user_id: Annotated[
        str,
        Depends(
            get_current_user_id
        ),
    ],
    service: Annotated[
        WatchlistService,
        Depends(
            get_watchlist_service
        ),
    ],
) -> WatchlistItemResponse:
    try:
        model = service.add_item(
            user_id=user_id,
            symbol=request.symbol,
        )

    except InvalidWatchlistSymbolError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc

    except WatchlistItemAlreadyExistsError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except WatchlistLimitExceededError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    return _to_response(
        model
    )


@router.delete(
    "/{symbol}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def delete_watchlist_item(
    symbol: str,
    user_id: Annotated[
        str,
        Depends(
            get_current_user_id
        ),
    ],
    service: Annotated[
        WatchlistService,
        Depends(
            get_watchlist_service
        ),
    ],
) -> Response:
    try:
        service.delete_item(
            user_id=user_id,
            symbol=symbol,
        )

    except InvalidWatchlistSymbolError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc

    except WatchlistItemNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )