from libs.database.models import (
    Base,
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)


def test_paper_trading_tables_are_registered() -> None:
    table_names = Base.metadata.tables

    assert "paper_accounts" in table_names
    assert "paper_positions" in table_names
    assert "paper_orders" in table_names
    assert "paper_executions" in table_names


def test_paper_position_has_account_symbol_unique_constraint() -> None:
    table = PaperPositionModel.__table__

    constraint_names = {
        constraint.name
        for constraint in table.constraints
    }

    assert (
        "uq_paper_positions_account_symbol"
        in constraint_names
    )


def test_paper_order_has_required_indexes() -> None:
    table = PaperOrderModel.__table__

    index_names = {
        index.name
        for index in table.indexes
    }

    assert "ix_paper_orders_account_id" in index_names
    assert "ix_paper_orders_account_status" in index_names
    assert "ix_paper_orders_symbol_status" in index_names


def test_paper_execution_references_order_and_account() -> None:
    table = PaperExecutionModel.__table__

    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in table.foreign_keys
    }

    assert "paper_orders.id" in foreign_keys
    assert "paper_accounts.id" in foreign_keys


def test_paper_account_has_user_index() -> None:
    table = PaperAccountModel.__table__

    index_names = {
        index.name
        for index in table.indexes
    }

    assert "ix_paper_accounts_user_id" in index_names