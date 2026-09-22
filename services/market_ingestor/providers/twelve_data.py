from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import SecretStr

TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
DEFAULT_TIMEOUT_SECONDS = 10.0

_SUPPORTED_TIME_SERIES_INTERVALS = frozenset(
    {
        "1min",
        "5min",
        "15min",
        "30min",
        "45min",
        "1h",
        "2h",
        "4h",
        "8h",
        "1day",
        "1week",
        "1month",
    }
)


class TwelveDataError(RuntimeError):
    """Base exception for Twelve Data provider failures."""


class TwelveDataRequestError(TwelveDataError):
    """Raised when the remote HTTP request fails."""


class TwelveDataResponseError(TwelveDataError):
    """Raised when Twelve Data returns an invalid or error response."""


@dataclass(frozen=True, slots=True)
class FiftyTwoWeekRange:
    low: Decimal
    high: Decimal
    low_change: Decimal
    high_change: Decimal
    low_change_percent: Decimal
    high_change_percent: Decimal
    range: str


@dataclass(frozen=True, slots=True)
class TwelveDataQuoteSnapshot:
    """
    Normalized Twelve Data OHLC quote snapshot.

    This type deliberately represents an OHLC market snapshot. It must not
    be confused with the RealStock MarketQuote domain model, which represents
    bid/ask semantics.
    """

    symbol: str
    name: str
    exchange: str
    mic_code: str
    currency: str

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    previous_close: Decimal
    change: Decimal
    percent_change: Decimal

    volume: int
    average_volume: int
    is_market_open: bool

    timestamp: datetime
    last_quote_at: datetime | None
    fifty_two_week: FiftyTwoWeekRange | None = None


@dataclass(frozen=True, slots=True)
class TwelveDataBatchQuoteResult:
    """
    Partial-success result from a Twelve Data batch quote request.

    One unavailable symbol must not invalidate successful symbols returned by
    the same upstream request.
    """

    quotes: dict[str, TwelveDataQuoteSnapshot]
    errors: dict[str, str]


@dataclass(frozen=True, slots=True)
class TwelveDataCandle:
    """
    Normalized Twelve Data time-series OHLC candle.

    The datetime value is kept in the upstream textual form because the API
    layer is responsible for serializing chart timestamps. Numeric market
    values remain Decimal inside the provider boundary.
    """

    datetime: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


def _decimal(
    value: object,
    *,
    field_name: str,
) -> Decimal:
    if value is None:
        raise TwelveDataResponseError(
            f"Missing field: {field_name}"
        )

    if isinstance(value, bool):
        raise TwelveDataResponseError(
            f"Invalid decimal field: {field_name}"
        )

    try:
        result = Decimal(str(value).strip())
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:
        raise TwelveDataResponseError(
            f"Invalid decimal field: {field_name}"
        ) from exc

    if not result.is_finite():
        raise TwelveDataResponseError(
            f"Invalid decimal field: {field_name}"
        )

    return result


def _integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if value is None:
        raise TwelveDataResponseError(
            f"Missing field: {field_name}"
        )

    if isinstance(value, bool):
        raise TwelveDataResponseError(
            f"Invalid integer field: {field_name}"
        )

    try:
        return int(str(value).strip())
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise TwelveDataResponseError(
            f"Invalid integer field: {field_name}"
        ) from exc


def _boolean(
    value: object,
    *,
    field_name: str,
) -> bool:
    """
    Parse a strict JSON boolean.

    The upstream contract defines is_market_open as a JSON boolean.
    String and numeric lookalikes must not be silently coerced.

    Accepted:
        true
        false

    Rejected:
        "true"
        "false"
        1
        0
        null
    """

    if not isinstance(value, bool):
        raise TwelveDataResponseError(
            f"Invalid boolean field: {field_name}"
        )

    return value


def _required_string(
    payload: dict[str, Any],
    field_name: str,
) -> str:
    value = payload.get(field_name)

    if value is None:
        raise TwelveDataResponseError(
            f"Missing field: {field_name}"
        )

    if not isinstance(value, str):
        raise TwelveDataResponseError(
            f"Invalid string field: {field_name}"
        )

    result = value.strip()

    if not result:
        raise TwelveDataResponseError(
            f"Empty field: {field_name}"
        )

    return result


def _timestamp(
    value: object,
    *,
    field_name: str,
) -> datetime:
    timestamp_value = _integer(
        value,
        field_name=field_name,
    )

    try:
        return datetime.fromtimestamp(
            timestamp_value,
            tz=UTC,
        )
    except (
        OSError,
        OverflowError,
        ValueError,
    ) as exc:
        raise TwelveDataResponseError(
            f"Invalid timestamp field: {field_name}"
        ) from exc


def _optional_timestamp(
    value: object,
    *,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            return None

        value = normalized

    return _timestamp(
        value,
        field_name=field_name,
    )


def _parse_fifty_two_week(
    payload: dict[str, Any],
) -> FiftyTwoWeekRange | None:
    if "fifty_two_week" not in payload:
        return None

    fifty_two_week_payload = payload.get(
        "fifty_two_week"
    )

    if fifty_two_week_payload is None:
        return None

    if not isinstance(
        fifty_two_week_payload,
        dict,
    ):
        raise TwelveDataResponseError(
            "Invalid field: fifty_two_week"
        )

    result = FiftyTwoWeekRange(
        low=_decimal(
            fifty_two_week_payload.get("low"),
            field_name="fifty_two_week.low",
        ),
        high=_decimal(
            fifty_two_week_payload.get("high"),
            field_name="fifty_two_week.high",
        ),
        low_change=_decimal(
            fifty_two_week_payload.get(
                "low_change"
            ),
            field_name=(
                "fifty_two_week.low_change"
            ),
        ),
        high_change=_decimal(
            fifty_two_week_payload.get(
                "high_change"
            ),
            field_name=(
                "fifty_two_week.high_change"
            ),
        ),
        low_change_percent=_decimal(
            fifty_two_week_payload.get(
                "low_change_percent"
            ),
            field_name=(
                "fifty_two_week."
                "low_change_percent"
            ),
        ),
        high_change_percent=_decimal(
            fifty_two_week_payload.get(
                "high_change_percent"
            ),
            field_name=(
                "fifty_two_week."
                "high_change_percent"
            ),
        ),
        range=_required_string(
            fifty_two_week_payload,
            "range",
        ),
    )

    if result.high < result.low:
        raise TwelveDataResponseError(
            "Invalid fifty_two_week range: "
            "high is lower than low"
        )

    return result


def _parse_quote_payload(
    payload: dict[str, Any],
) -> TwelveDataQuoteSnapshot:
    return TwelveDataQuoteSnapshot(
        symbol=_required_string(
            payload,
            "symbol",
        ).upper(),
        name=_required_string(
            payload,
            "name",
        ),
        exchange=_required_string(
            payload,
            "exchange",
        ),
        mic_code=_required_string(
            payload,
            "mic_code",
        ),
        currency=_required_string(
            payload,
            "currency",
        ).upper(),
        open=_decimal(
            payload.get("open"),
            field_name="open",
        ),
        high=_decimal(
            payload.get("high"),
            field_name="high",
        ),
        low=_decimal(
            payload.get("low"),
            field_name="low",
        ),
        close=_decimal(
            payload.get("close"),
            field_name="close",
        ),
        previous_close=_decimal(
            payload.get("previous_close"),
            field_name="previous_close",
        ),
        change=_decimal(
            payload.get("change"),
            field_name="change",
        ),
        percent_change=_decimal(
            payload.get("percent_change"),
            field_name="percent_change",
        ),
        volume=_integer(
            payload.get("volume"),
            field_name="volume",
        ),
        average_volume=_integer(
            payload.get("average_volume"),
            field_name="average_volume",
        ),
        is_market_open=_boolean(
            payload.get("is_market_open"),
            field_name="is_market_open",
        ),
        timestamp=_timestamp(
            payload.get("timestamp"),
            field_name="timestamp",
        ),
        last_quote_at=_optional_timestamp(
            payload.get("last_quote_at"),
            field_name="last_quote_at",
        ),
        fifty_two_week=_parse_fifty_two_week(
            payload
        ),
    )


def _parse_expected_quote(
    payload: dict[str, Any],
    *,
    expected_symbol: str,
) -> TwelveDataQuoteSnapshot:
    quote = _parse_quote_payload(payload)

    if quote.symbol != expected_symbol:
        raise TwelveDataResponseError(
            "Twelve Data quote symbol does not "
            "match requested symbol"
        )

    return quote


class TwelveDataMarketDataProvider:
    """
    REST client for Twelve Data market data.

    Responsibilities:

        Twelve Data HTTPS API
                ↓
        response validation
                ↓
        normalized Decimal values
                ↓
        quote snapshots / time-series candles

    API credentials are sent only through the Authorization header and must
    never be included in query strings or application logs.
    """

    def __init__(
        self,
        *,
        api_key: SecretStr | str,
        base_url: str = TWELVE_DATA_BASE_URL,
        timeout_seconds: float = (
            DEFAULT_TIMEOUT_SECONDS
        ),
        client: httpx.Client | None = None,
    ) -> None:
        if isinstance(api_key, SecretStr):
            secret = (
                api_key.get_secret_value().strip()
            )
        else:
            secret = api_key.strip()

        if not secret:
            raise ValueError(
                "api_key must not be empty"
            )

        normalized_base_url = (
            base_url.strip().rstrip("/")
        )

        if not normalized_base_url:
            raise ValueError(
                "base_url must not be empty"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater "
                "than zero"
            )

        self._api_key = secret
        self._base_url = normalized_base_url
        self._timeout_seconds = timeout_seconds
        self._client = (
            client
            if client is not None
            else httpx.Client(
                timeout=timeout_seconds
            )
        )
        self._owns_client = client is None

    def __enter__(
        self,
    ) -> TwelveDataMarketDataProvider:
        return self

    def __exit__(
        self,
        _exc_type: object,
        _exc_value: object,
        _traceback: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": (
                f"apikey {self._api_key}"
            ),
            "Accept": "application/json",
            "User-Agent": (
                "RealStock-Enterprise/1.0"
            ),
        }

    def _request(
        self,
        *,
        endpoint: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        url = (
            f"{self._base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        try:
            response = self._client.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TwelveDataRequestError(
                "Twelve Data request failed"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TwelveDataResponseError(
                "Twelve Data returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise TwelveDataResponseError(
                "Twelve Data response must be "
                "a JSON object"
            )

        if payload.get("status") == "error":
            code = payload.get(
                "code",
                "unknown",
            )
            message = payload.get(
                "message",
                "Unknown Twelve Data error",
            )

            raise TwelveDataResponseError(
                "Twelve Data API error "
                f"code={code}: {message}"
            )

        return payload

    def get_time_series(
        self,
        symbol: str,
        *,
        interval: str,
        outputsize: int,
    ) -> list[TwelveDataCandle]:
        """
        Retrieve chronological OHLC candles from Twelve Data.

        The provider requests ascending data so callers can pass the returned
        sequence directly to a charting layer.
        """

        normalized_symbol = (
            symbol.strip().upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        normalized_interval = (
            interval.strip().lower()
        )

        if (
            normalized_interval
            not in _SUPPORTED_TIME_SERIES_INTERVALS
        ):
            raise ValueError(
                "unsupported time-series interval: "
                f"{interval}"
            )

        if outputsize < 1:
            raise ValueError(
                "outputsize must be positive"
            )

        if outputsize > 5000:
            raise ValueError(
                "outputsize must not exceed 5000"
            )

        payload = self._request(
            endpoint="time_series",
            params={
                "symbol": normalized_symbol,
                "interval": normalized_interval,
                "outputsize": str(outputsize),
                "order": "asc",
                "timezone": "UTC",
            },
        )

        raw_values = payload.get("values")

        if not isinstance(raw_values, list):
            raise TwelveDataResponseError(
                "Twelve Data time-series response "
                "must contain a values list"
            )

        candles: list[TwelveDataCandle] = []

        for index, raw_item in enumerate(
            raw_values
        ):
            if not isinstance(raw_item, dict):
                raise TwelveDataResponseError(
                    "Invalid time-series item "
                    f"at index {index}"
                )

            candle = TwelveDataCandle(
                datetime=_required_string(
                    raw_item,
                    "datetime",
                ),
                open=_decimal(
                    raw_item.get("open"),
                    field_name="open",
                ),
                high=_decimal(
                    raw_item.get("high"),
                    field_name="high",
                ),
                low=_decimal(
                    raw_item.get("low"),
                    field_name="low",
                ),
                close=_decimal(
                    raw_item.get("close"),
                    field_name="close",
                ),
            )

            if candle.high < candle.low:
                raise TwelveDataResponseError(
                    "Invalid time-series OHLC: "
                    "high is lower than low"
                )

            if not (
                candle.low
                <= candle.open
                <= candle.high
            ):
                raise TwelveDataResponseError(
                    "Invalid time-series OHLC: "
                    "open is outside high/low range"
                )

            if not (
                candle.low
                <= candle.close
                <= candle.high
            ):
                raise TwelveDataResponseError(
                    "Invalid time-series OHLC: "
                    "close is outside high/low range"
                )

            candles.append(candle)

        return candles

    def get_price(
        self,
        symbol: str,
    ) -> Decimal:
        normalized_symbol = (
            symbol.strip().upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        payload = self._request(
            endpoint="price",
            params={
                "symbol": normalized_symbol,
            },
        )

        return _decimal(
            payload.get("price"),
            field_name="price",
        )

    def get_quote(
        self,
        symbol: str,
    ) -> TwelveDataQuoteSnapshot:
        normalized_symbol = (
            symbol.strip().upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        payload = self._request(
            endpoint="quote",
            params={
                "symbol": normalized_symbol,
            },
        )

        return _parse_expected_quote(
            payload,
            expected_symbol=normalized_symbol,
        )

    def get_quotes(
        self,
        symbols: list[str],
    ) -> TwelveDataBatchQuoteResult:
        """
        Retrieve multiple quote snapshots with one Twelve Data request.

        Successful and failed symbols are returned independently so a partial
        upstream failure does not discard valid quote snapshots.
        """

        normalized_symbols: list[str] = []
        seen: set[str] = set()

        for symbol in symbols:
            normalized = symbol.strip().upper()

            if not normalized:
                raise ValueError(
                    "symbols must not contain "
                    "empty values"
                )

            if normalized in seen:
                continue

            seen.add(normalized)
            normalized_symbols.append(normalized)

        if not normalized_symbols:
            raise ValueError(
                "symbols must not be empty"
            )

        payload = self._request(
            endpoint="quote",
            params={
                "symbol": ",".join(
                    normalized_symbols
                ),
            },
        )

        quotes: dict[
            str,
            TwelveDataQuoteSnapshot,
        ] = {}
        errors: dict[str, str] = {}

        # Twelve Data returns a normal single-symbol quote object when only
        # one symbol is supplied.
        if (
            len(normalized_symbols) == 1
            and "symbol" in payload
        ):
            symbol = normalized_symbols[0]

            try:
                quotes[symbol] = (
                    _parse_expected_quote(
                        payload,
                        expected_symbol=symbol,
                    )
                )
            except TwelveDataResponseError:
                errors[symbol] = (
                    "Invalid market data response."
                )

            return TwelveDataBatchQuoteResult(
                quotes=quotes,
                errors=errors,
            )

        normalized_payload = {
            str(key).strip().upper(): value
            for key, value in payload.items()
        }

        for symbol in normalized_symbols:
            raw_symbol_payload = (
                normalized_payload.get(symbol)
            )

            if not isinstance(
                raw_symbol_payload,
                dict,
            ):
                errors[symbol] = (
                    "Market data was not returned."
                )
                continue

            if (
                raw_symbol_payload.get("status")
                == "error"
            ):
                errors[symbol] = (
                    "Market data provider rejected "
                    "the symbol or quota request."
                )
                continue

            try:
                quotes[symbol] = (
                    _parse_expected_quote(
                        raw_symbol_payload,
                        expected_symbol=symbol,
                    )
                )
            except TwelveDataResponseError:
                errors[symbol] = (
                    "Invalid market data response."
                )

        return TwelveDataBatchQuoteResult(
            quotes=quotes,
            errors=errors,
        )
