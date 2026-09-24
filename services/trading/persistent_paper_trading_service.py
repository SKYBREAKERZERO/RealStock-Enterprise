from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from libs.database.unit_of_work import UnitOfWork
from libs.trading.execution import Execution
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
    - Process persisted LIMIT orders against live quotes.
    - Cancel persisted LIMIT orders atomically.
    - Commit each application operation atomically.

    Transaction ownership belongs to UnitOfWork.

    MARKET / LIMIT submission lock ordering:

        Account FOR UPDATE
            ->
        Position FOR UPDATE
            ->
        domain operation
            ->
        persistence
            ->
        commit

    Persisted LIMIT processing lock ordering:

        routing order read
            ->
        Account FOR UPDATE
            ->
        Order FOR UPDATE
            ->
        Position FOR UPDATE
            ->
        domain operation
            ->
        persistence
            ->
        commit

    Persisted LIMIT cancellation lock ordering:

        routing order read
            ->
        Account FOR UPDATE
            ->
        Order FOR UPDATE
            ->
        domain cancellation
            ->
        order update
            ->
        commit

    The account row is the primary per-account serialization point.

    For persisted LIMIT processing and cancellation, the first unlocked
    order read is used only to discover the account_id needed to establish
    the account-first locking order. No trading or cancellation decision
    may be made from that unlocked order copy.
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
    # PERSISTED LIMIT PROCESSING
    # ==========================================================

    def process_limit_order(
        self,
        *,
        order_id: UUID,
    ) -> Execution | None:
        """
        Process one persisted LIMIT order against the latest quote.

        The application receives only order_id. To preserve the
        canonical account-first locking strategy, an initial unlocked
        order read is used exclusively to discover account_id.

        No execution decision is made using that first order object.

        Transaction sequence:

            unlocked order routing read
                ->
            account FOR UPDATE
                ->
            order FOR UPDATE
                ->
            position FOR UPDATE
                ->
            PaperTradingService.process_limit_order()
                ->
            persistence
                ->
            commit

        If the current quote does not satisfy the LIMIT condition,
        no execution is generated and account / position / order
        trading state remains unchanged.

        If the order fills, account, position, existing order and
        execution are persisted atomically.
        """

        with self.unit_of_work:
            routing_order = (
                self.unit_of_work
                .paper_orders
                .get(
                    order_id
                )
            )

            if routing_order is None:
                raise ValueError(
                    f"Paper order {order_id} not found."
                )

            account = self._require_account_for_update(
                routing_order.account_id
            )

            order = (
                self.unit_of_work
                .paper_orders
                .get_for_update(
                    order_id
                )
            )

            if order is None:
                raise ValueError(
                    f"Paper order {order_id} not found."
                )

            if order.account_id != account.account_id:
                raise RuntimeError(
                    "Paper order account changed while "
                    "acquiring transaction locks."
                )

            position = (
                self._get_or_create_position_for_update(
                    account_id=order.account_id,
                    symbol=order.symbol,
                )
            )

            execution = (
                self.trading_service
                .process_limit_order(
                    account=account,
                    position=position,
                    order=order,
                )
            )

            if execution is None:
                self.unit_of_work.commit()

                return None

            self._persist_limit_execution(
                account=account,
                position=position,
                order=order,
                execution=execution,
            )

            self.unit_of_work.commit()

            return execution

    # ==========================================================
    # PERSISTED LIMIT CANCELLATION
    # ==========================================================

    def cancel_limit_order(
        self,
        *,
        order_id: UUID,
    ) -> PaperOrder:
        """
        Cancel one persisted LIMIT order atomically.

        The application receives only order_id. To preserve the
        canonical account-first locking strategy, an initial unlocked
        order read is used exclusively to discover account_id.

        No cancellation decision is made using that first order object.

        Transaction sequence:

            unlocked order routing read
                ->
            account FOR UPDATE
                ->
            order FOR UPDATE
                ->
            PaperTradingService.cancel_order()
                ->
            order UPDATE
                ->
            commit

        Cancellation changes only the persisted order lifecycle state.
        It does not modify account cash, positions, or executions.
        """

        with self.unit_of_work:
            routing_order = (
                self.unit_of_work
                .paper_orders
                .get(
                    order_id
                )
            )

            if routing_order is None:
                raise ValueError(
                    f"Paper order {order_id} not found."
                )

            account = self._require_account_for_update(
                routing_order.account_id
            )

            order = (
                self.unit_of_work
                .paper_orders
                .get_for_update(
                    order_id
                )
            )

            if order is None:
                raise ValueError(
                    f"Paper order {order_id} not found."
                )

            if order.account_id != account.account_id:
                raise RuntimeError(
                    "Paper order account changed while "
                    "acquiring transaction locks."
                )

            self.trading_service.cancel_order(
                order=order
            )

            self.unit_of_work.paper_orders.update(
                order
            )

            self.unit_of_work.commit()

            return order

    # ==========================================================
    # MARKET EXECUTION PERSISTENCE
    # ==========================================================

    def _persist_execution(
        self,
        *,
        account: PaperAccount,
        position: Position,
        result: TradeExecutionResult,
    ) -> None:
        """
        Persist all state produced by a successful MARKET execution.

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
    # LIMIT EXECUTION PERSISTENCE
    # ==========================================================

    def _persist_limit_execution(
        self,
        *,
        account: PaperAccount,
        position: Position,
        order: PaperOrder,
        execution: Execution,
    ) -> None:
        """
        Persist execution of an already-existing LIMIT order.

        Unlike a MARKET order, the LIMIT order already exists in
        PostgreSQL because it was persisted when submitted.

        Therefore:

            MARKET execution:
                paper_orders.add(...)

            persisted LIMIT execution:
                paper_orders.update(...)

        The existing order must never be inserted a second time.

        The UnitOfWork owns the final commit / rollback boundary.
        """

        account_id = account.account_id

        if account_id is None:
            raise RuntimeError(
                "Paper account must have an account_id "
                "before persistence."
            )

        if order.account_id != account_id:
            raise RuntimeError(
                "Paper order does not belong to "
                "the locked account."
            )

        if execution.order_id != order.order_id:
            raise RuntimeError(
                "Execution does not belong to "
                "the processed paper order."
            )

        self.unit_of_work.paper_accounts.update(
            account
        )

        self.unit_of_work.paper_positions.upsert(
            account_id=account_id,
            position=position,
        )

        self.unit_of_work.paper_orders.update(
            order
        )

        self.unit_of_work.paper_executions.add(
            account_id=account_id,
            execution=execution,
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