from decimal import Decimal

import pytest

from libs.trading.exceptions import (
    InsufficientBuyingPowerError,
)
from libs.trading.models import PaperAccount


def test_account_starts_with_initial_cash() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    assert account.cash_balance == Decimal("100000")
    assert account.buying_power == Decimal("100000")


def test_account_rejects_insufficient_buying_power() -> None:
    account = PaperAccount(
        initial_cash=Decimal("1000"),
    )

    with pytest.raises(
        InsufficientBuyingPowerError
    ):
        account.ensure_can_buy(
            quantity=10,
            estimated_price=Decimal("200"),
        )


def test_account_can_debit_and_credit_cash() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    account.debit(Decimal("25000"))

    assert account.cash_balance == Decimal("75000")

    account.credit(Decimal("5000"))

    assert account.cash_balance == Decimal("80000")