import pytest
from core.sql_guard import guard, GuardError, HallucinationError


def test_select_passes():
    sql = guard("SELECT id, name FROM customers")
    assert "SELECT" in sql.upper()


def test_limit_injected():
    sql = guard("SELECT id FROM customers")
    assert "LIMIT 100" in sql


def test_limit_not_duplicated():
    sql = guard("SELECT id FROM customers LIMIT 10")
    assert sql.upper().count("LIMIT") == 1


def test_insert_blocked():
    with pytest.raises(GuardError):
        guard("INSERT INTO customers VALUES (1,'x',1,'2024-01-01')")


def test_update_blocked():
    with pytest.raises(GuardError):
        guard("UPDATE customers SET name='x' WHERE id=1")


def test_delete_blocked():
    with pytest.raises(GuardError):
        guard("DELETE FROM customers WHERE id=1")


def test_drop_blocked():
    with pytest.raises(GuardError):
        guard("DROP TABLE customers")


def test_alter_blocked():
    with pytest.raises(GuardError):
        guard("ALTER TABLE customers ADD COLUMN foo TEXT")


def test_pragma_blocked():
    with pytest.raises(GuardError):
        guard("PRAGMA table_info(customers)")


def test_multiple_statements_blocked():
    with pytest.raises(GuardError):
        guard("SELECT 1; DROP TABLE customers")


def test_hallucinated_table_caught():
    with pytest.raises(HallucinationError):
        guard("SELECT * FROM nonexistent_table")


def test_hallucinated_column_caught():
    with pytest.raises(HallucinationError):
        guard("SELECT c.ghost_column FROM customers c")


def test_cte_select_allowed():
    sql = guard("""
        WITH top_orders AS (
            SELECT order_id, SUM(quantity) AS total_qty FROM order_items GROUP BY order_id
        )
        SELECT * FROM top_orders ORDER BY total_qty DESC LIMIT 5
    """)
    assert sql is not None


def test_aggregate_only_no_limit():
    sql = guard("SELECT COUNT(*) AS total FROM orders")
    assert "LIMIT" not in sql


def test_read_only_select():
    sql = guard("SELECT * FROM restaurants LIMIT 5")
    assert sql is not None
