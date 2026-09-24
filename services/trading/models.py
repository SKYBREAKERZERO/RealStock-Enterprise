from __future__ import annotations

from dataclasses import dataclass

from libs.trading.execution import Execution
from libs.trading.models import PaperOrder


@dataclass(
    frozen=True,
    slots=True,
)
class TradeExecutionResult:
    order: PaperOrder
    execution: Execution