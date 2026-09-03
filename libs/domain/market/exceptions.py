from __future__ import annotations


class MarketDomainError(Exception):
    """
    Base exception for all market-domain errors.
    """


class InvalidSymbolError(MarketDomainError):
    """
    Raised when a market symbol is invalid.
    """


class InvalidPriceError(MarketDomainError):
    """
    Raised when a market price is invalid.
    """


class InvalidQuantityError(MarketDomainError):
    """
    Raised when a market quantity is invalid.
    """


class InvalidTimestampError(MarketDomainError):
    """
    Raised when a market timestamp is invalid.
    """


class UnsupportedMarketError(MarketDomainError):
    """
    Raised when the requested market is not supported.
    """


class MarketDataValidationError(MarketDomainError):
    """
    Raised when market data violates domain validation rules.
    """