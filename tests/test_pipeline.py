"""Integration tests for core.db — requires the generated DB to exist."""
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import config
from core.db import execute_query, QueryError


@pytest.mark.skipif(not config.DB_PATH.exists(), reason="DB not yet generated — run python data/generate_data.py first")
class TestDB:
    def test_basic_select(self):
        df = execute_query("SELECT COUNT(*) AS n FROM orders")
        assert df["n"].iloc[0] == 30000

    def test_delivered_orders(self):
        df = execute_query("SELECT COUNT(*) AS n FROM orders WHERE status='delivered'")
        assert df["n"].iloc[0] > 20000

    def test_customers(self):
        df = execute_query("SELECT COUNT(*) AS n FROM customers")
        assert df["n"].iloc[0] == 8000

    def test_read_only_enforced(self):
        with pytest.raises(Exception):
            execute_query("INSERT INTO customers VALUES (99999,'Test',1,'2024-01-01')")

    def test_monthly_revenue_query(self):
        df = execute_query(
            "SELECT strftime('%Y-%m', order_time) AS month, SUM(total_amount) AS total_revenue "
            "FROM orders WHERE status='delivered' GROUP BY month ORDER BY month ASC LIMIT 18"
        )
        assert len(df) > 0
        assert "total_revenue" in df.columns
