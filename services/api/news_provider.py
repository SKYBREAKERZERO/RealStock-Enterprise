from __future__ import annotations

import html
import re
from datetime import datetime

import httpx
from pydantic import SecretStr

from services.api.schemas.news import NewsItem

_HTML_TAG_PATTERN = re.compile(
    r"<[^>]+>"
)

_WHITESPACE_PATTERN = re.compile(
    r"\s+"
)


class NewsProviderError(
    RuntimeError
):
    """Base error for news provider failures."""


class NewsProviderRequestError(
    NewsProviderError
):
    """Raised when an upstream request cannot be completed."""


class NewsProviderResponseError(
    NewsProviderError
):
    """Raised when the provider returns an invalid response."""


class TwelveDataNewsProvider:
    """
    Twelve Data press-release provider.

    Multiple watchlist symbols are sent as a single
    comma-separated request to reduce latency and
    API-credit consumption.
    """

    _BASE_URL = (
        "https://api.twelvedata.com"
    )

    _MAX_PAGE_SIZE = 10

    _MAX_PAGES = 5

    def __init__(
        self,
        *,
        api_key: SecretStr,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=self._BASE_URL,
            headers={
                "Authorization": (
                    "apikey "
                    + api_key.get_secret_value()
                ),
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(
                timeout_seconds,
            ),
        )

    def close(
        self,
    ) -> None:
        self._client.close()

    def get_latest(
        self,
        *,
        symbols: list[str],
        limit: int,
        language: str = "en",
    ) -> list[NewsItem]:
        normalized_symbols = (
            self._normalize_symbols(
                symbols
            )
        )

        if not normalized_symbols:
            return []

        if limit < 1:
            return []

        requested_limit = min(
            limit,
            20,
        )

        symbol_parameter = (
            ",".join(
                normalized_symbols
            )
        )

        unique_items: dict[
            str,
            NewsItem,
        ] = {}

        page = 1

        while (
            len(unique_items)
            < requested_limit
            and page
            <= self._MAX_PAGES
        ):
            remaining = (
                requested_limit
                - len(unique_items)
            )

            output_size = min(
                max(
                    remaining,
                    1,
                ),
                self._MAX_PAGE_SIZE,
            )

            payload = self._request_page(
                symbols=(
                    symbol_parameter
                ),
                language=language,
                output_size=(
                    output_size
                ),
                page=page,
            )

            releases = payload.get(
                "press_releases"
            )

            if releases is None:
                raise (
                    NewsProviderResponseError(
                        "Twelve Data response "
                        "does not contain "
                        "press_releases."
                    )
                )

            if not isinstance(
                releases,
                list,
            ):
                raise (
                    NewsProviderResponseError(
                        "Twelve Data "
                        "press_releases "
                        "must be a list."
                    )
                )

            if not releases:
                break

            for raw_item in releases:
                item = self._parse_item(
                    raw_item
                )

                if item is None:
                    continue

                unique_items[
                    item.id
                ] = item

            if (
                len(releases)
                < output_size
            ):
                break

            page += 1

        items = list(
            unique_items.values()
        )

        items.sort(
            key=lambda item: (
                item.published_at
            ),
            reverse=True,
        )

        return items[
            :requested_limit
        ]

    def _request_page(
        self,
        *,
        symbols: str,
        language: str,
        output_size: int,
        page: int,
    ) -> dict[str, object]:
        try:
            response = (
                self._client.get(
                    "/press_releases",
                    params={
                        "symbol": symbols,
                        "language": (
                            language
                        ),
                        "outputsize": (
                            output_size
                        ),
                        "page": page,
                    },
                )
            )

        except httpx.RequestError as exc:
            raise (
                NewsProviderRequestError(
                    "Unable to connect "
                    "to Twelve Data."
                )
            ) from exc

        if response.is_error:
            message = (
                self._get_error_message(
                    response
                )
            )

            raise (
                NewsProviderResponseError(
                    "Twelve Data returned "
                    f"HTTP "
                    f"{response.status_code}: "
                    f"{message}"
                )
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise (
                NewsProviderResponseError(
                    "Twelve Data returned "
                    "invalid JSON."
                )
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise (
                NewsProviderResponseError(
                    "Unexpected Twelve Data "
                    "response structure."
                )
            )

        if (
            payload.get("status")
            == "error"
        ):
            message = payload.get(
                "message"
            )

            if not isinstance(
                message,
                str,
            ):
                message = (
                    "Unknown provider error."
                )

            raise (
                NewsProviderResponseError(
                    message
                )
            )

        return payload

    @staticmethod
    def _normalize_symbols(
        symbols: list[str],
    ) -> list[str]:
        result: list[str] = []

        seen: set[str] = set()

        for symbol in symbols:
            normalized = (
                symbol
                .strip()
                .upper()
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return result

    @staticmethod
    def _parse_item(
        raw_item: object,
    ) -> NewsItem | None:
        if not isinstance(
            raw_item,
            dict,
        ):
            return None

        raw_id = raw_item.get(
            "id"
        )

        raw_datetime = raw_item.get(
            "datetime"
        )

        raw_title = raw_item.get(
            "title"
        )

        raw_body = raw_item.get(
            "body"
        )

        if not isinstance(
            raw_id,
            str,
        ):
            return None

        if not isinstance(
            raw_datetime,
            str,
        ):
            return None

        if not isinstance(
            raw_title,
            str,
        ):
            return None

        normalized_id = (
            raw_id.strip()
        )

        title = raw_title.strip()

        if not normalized_id:
            return None

        if not title:
            return None

        try:
            published_at = (
                datetime.fromisoformat(
                    raw_datetime.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

        except ValueError:
            return None

        body = (
            raw_body
            if isinstance(
                raw_body,
                str,
            )
            else ""
        )

        summary = (
            TwelveDataNewsProvider
            ._build_summary(
                body
            )
        )

        if not summary:
            summary = title

        return NewsItem(
            id=normalized_id,
            published_at=(
                published_at
            ),
            title=title,
            summary=summary,
            source="Twelve Data",
            url=None,
        )

    @staticmethod
    def _build_summary(
        body: str,
        *,
        max_length: int = 280,
    ) -> str:
        without_tags = (
            _HTML_TAG_PATTERN.sub(
                " ",
                body,
            )
        )

        decoded = html.unescape(
            without_tags
        )

        normalized = (
            _WHITESPACE_PATTERN.sub(
                " ",
                decoded,
            )
            .strip()
        )

        if (
            len(normalized)
            <= max_length
        ):
            return normalized

        shortened = normalized[
            : max_length - 1
        ]

        last_space = (
            shortened.rfind(
                " "
            )
        )

        if last_space > 0:
            shortened = shortened[
                :last_space
            ]

        return (
            shortened.rstrip()
            + "…"
        )

    @staticmethod
    def _get_error_message(
        response: httpx.Response,
    ) -> str:
        try:
            payload = response.json()

        except ValueError:
            return (
                "invalid provider "
                "response"
            )

        if isinstance(
            payload,
            dict,
        ):
            message = payload.get(
                "message"
            )

            if isinstance(
                message,
                str,
            ):
                return message

        return (
            "unknown provider error"
        )