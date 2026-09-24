from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from libs.database.unit_of_work import UnitOfWork
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from services.trading.models import TradeExecutionResult
from services.trading.paper_trading_service import (
    PaperTradingService,
)


@dataclass(slots=True)
class PersistentPaperTradingService:
    """
    Persistent application service for paper trading.

    Responsibilities:
    - Load paper-trading state through UnitOfWork repositories.
    - Acquire pessimistic row locks before state-changing operations.
    - Delegate trading semantics to PaperTradingService.
    - Persist accounts, positions, orders, and executions.
    - Persist pending LIMIT orders.
    - Commit each application operation atomically.

    Transaction ownership belongs to UnitOfWork.

    Lock ordering:

        Account FOR UPDATE
            ->
        Position FOR UPDATE
            ->
        domain operation
            ->
        persistence
            ->
        commit

    The account row is the primary per-account serialization point.
    """

    trading_service: PaperTradingService
    unit_of_work: UnitOfWork

    # ==========================================================
    # MARKET BUY
    # ==========================================================

    def market_buy(
        self,
        *,
        account_id: UUID,
        symbol: str,
        quantity: int,
    ) -> TradeExecutionResult:
        """
        Execute and persist a MARKET BUY.

        The current ask price is used by PaperTradingService /
        PaperBroker.

        Persistence is atomic:

        - account state;
        - position state;
        - FILLED order;
        - execution.
        """

        normalized_symbol = self._normalize_symbol(
            symbol
        )

        with self.unit_of_work:
            account = self._require_account_for_update(
                account_id
            )

            position = (
                self._get_or_create_position_for_update(
                    account_id=account_id,
                    symbol=normalized_symbol,
                )
            )

            result = self.trading_service.market_buy(
                account=account,
                position=position,
                quantity=quantity,
            )

            self._persist_execution(
                account=account,
                position=position,
                result=result,
            )

            self.unit_of_work.commit()

            return result

    # ==========================================================
    # MARKET SELL
    # ==========================================================

    def market_sell(
        self,
        *,
        account_id: UUID,
        symbol: str,
        quantity: int,
    ) -> TradeExecutionResult:
        """
        Execute and persist a MARKET SELL.

        The current bid price is used by PaperTradingService /
        PaperBroker.

        Persistence is atomic:

        - account state;
        - position state;
        - FILLED order;
        - execution.
        """

        normalized_symbol = self._normalize_symbol(
            symbol
        )

        with self.unit_of_work:
            account = self._require_account_for_update(
                account_id
            )

            position = (
                self._get_or_create_position_for_update(
                    account_id=account_id,
                    symbol=normalized_symbol,
                )
            )

            result = self.trading_service.market_sell(
                account=account,
                position=position,
                quantity=quantity,
            )

            self._persist_execution(
                account=account,
                position=position,
                result=result,
            )

            self.unit_of_work.commit()

            return result

    # ==========================================================
    # LIMIT BUY SUBMISSION
    # ==========================================================

    def submit_limit_buy(
        self,
        *,
        account_id: UUID,
        symbol: str,
        quantity: int,
        limit_price: Decimal,
    ) -> PaperOrder:
        """
        Submit and persist a LIMIT BUY order.

        Submission creates a PENDING order.

        It does not persist:
        - account cash changes;
        - position changes;
        - execution records.

        Execution occurs later when the order is processed against
        a live quote.
        """

        normalized_symbol = self._normalize_symbol(
            symbol
        )

        with self.unit_of_work:
            account = self._require_account_for_update(
                account_id
            )

            position = (
                self._get_or_create_position_for_update(
                    account_id=account_id,
                    symbol=normalized_symbol,
                )
            )

            order = self.trading_service.submit_limit_buy(
                account=account,
                position=position,
                quantity=quantity,
                limit_price=limit_price,
            )

            self.unit_of_work.paper_orders.add(
                order
            )

            self.unit_of_work.commit()

            return order

    # ==========================================================
    # LIMIT SELL SUBMISSION
    # ==========================================================

    def submit_limit_sell(
        self,
        *,
        account_id: UUID,
        symbol: str,
        quantity: int,
        limit_price: Decimal,
    ) -> PaperOrder:
        """
        Submit and persist a LIMIT SELL order.

        Submission creates a PENDING order.

        It does not persist:
        - account cash changes;
        - position changes;
        - execution records.

        Position quantity is not reserved at submission time.
        Availability is checked when the order is processed.
        """

        normalized_symbol = self._normalize_symbol(
            symbol
        )

        with self.unit_of_work:
            account = self._require_account_for_update(
                account_id
            )

            position = (
                self._get_or_create_position_for_update(
                    account_id=account_id,
                    symbol=normalized_symbol,
                )
            )

            order = self.trading_service.submit_limit_sell(
                account=account,
                position=position,
                quantity=quantity,
                limit_price=limit_price,
            )

            self.unit_of_work.paper_orders.add(
                order
            )

            self.unit_of_work.commit()

            return order

    # ==========================================================
    # EXECUTION PERSISTENCE
    # ==========================================================

    def _persist_execution(
        self,
        *,
        account: PaperAccount,
        position: Position,
        result: TradeExecutionResult,
    ) -> None:
        """
        Persist all state produced by a successful execution.

        Repository methods do not own the final transaction boundary.

        PaperOrderRepository.add() may flush the order before the
        execution insert so PostgreSQL can satisfy the
        paper_executions -> paper_orders foreign-key dependency.

        UnitOfWork owns commit and rollback.
        """

        account_id = account.account_id

        if account_id is None:
            raise RuntimeError(
                "Paper account must have an account_id "
                "before persistence."
            )

        self.unit_of_work.paper_accounts.update(
            account
        )

        self.unit_of_work.paper_positions.upsert(
            account_id=account_id,
            position=position,
        )

        self.unit_of_work.paper_orders.add(
            result.order
        )

        self.unit_of_work.paper_executions.add(
            account_id=account_id,
            execution=result.execution,
        )

    # ==========================================================
    # ACCOUNT LOCK
    # ==========================================================

    def _require_account_for_update(
        self,
        account_id: UUID,
    ) -> PaperAccount:
        """
        Load the paper account under a pessimistic row lock.

        PostgreSQL repository implementation uses:

            SELECT ... FOR UPDATE

        The account row is the primary serialization point for
        trading operations belonging to the same account.
        """

        account = (
            self.unit_of_work
            .paper_accounts
            .get_for_update(
                account_id
            )
        )

        if account is None:
            raise ValueError(
                f"Paper account {account_id} not found."
            )

        return account

    # ==========================================================
    # POSITION LOCK
    # ==========================================================

    def _get_or_create_position_for_update(
        self,
        *,
        account_id: UUID,
        symbol: str,
    ) -> Position:
        """
        Load and lock an existing position.

        If no persisted position exists, return an empty domain
        Position.

        A missing database row cannot itself be locked. Because the
        account row has already been locked, correctly implemented
        trading operations for the same account remain serialized.
        """

        position = (
            self.unit_of_work
            .paper_positions
            .get_for_update(
                account_id=account_id,
                symbol=symbol,
            )
        )

        if position is not None:
            return position

        return Position(
            symbol=symbol,
        )

    # ==========================================================
    # SYMBOL NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        """
        Normalize and validate a market symbol before opening the
        UnitOfWork transaction.
        """

        normalized_symbol = (
            symbol
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        return normalized_symbol