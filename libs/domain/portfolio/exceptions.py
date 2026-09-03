from __future__ import annotations


class PortfolioDomainError(Exception):
    """
    Base exception for portfolio-domain errors.
    """


class InvalidPortfolioNameError(PortfolioDomainError):
    """
    Raised when a portfolio name violates domain rules.
    """


class InvalidUserIdError(PortfolioDomainError):
    """
    Raised when a user identifier is invalid.
    """


class InvalidPositionError(PortfolioDomainError):
    """
    Raised when a position violates domain rules.
    """


class DuplicatePositionError(PortfolioDomainError):
    """
    Raised when the same market/symbol exists more than once
    inside a portfolio aggregate.
    """