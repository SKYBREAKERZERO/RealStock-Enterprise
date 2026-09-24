class TradingError(Exception):
    """Base exception for trading domain errors."""


class InsufficientBuyingPowerError(TradingError):
    """Raised when an account does not have enough buying power."""


class InsufficientPositionError(TradingError):
    """Raised when attempting to sell more shares than are held."""


class InvalidOrderError(TradingError):
    """Raised when an order is invalid."""