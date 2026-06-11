import pandas as pd
import pytest
from unittest.mock import MagicMock
from core.charts import build_chart


def _plan(hint="bar", title="Test"):
    p = MagicMock()
    p.chart_hint = hint
    p.title = title
    return p


def test_stat_card_single_row():
    df = pd.DataFrame({"total_orders": [42]})
    fig = build_chart(df, _plan("stat"))
    assert fig is not None
    # Indicator trace
    assert fig.data[0].type == "indicator"


def test_line_chart_temporal():
    df = pd.DataFrame({
        "month": ["2025-01", "2025-02", "2025-03"],
        "total_revenue": [100.0, 200.0, 150.0],
    })
    fig = build_chart(df, _plan("line"))
    assert fig is not None


def test_pie_chart():
    df = pd.DataFrame({
        "payment_method": ["cash", "card", "easypaisa"],
        "count": [100, 200, 50],
    })
    fig = build_chart(df, _plan("pie"))
    assert fig is not None


def test_bar_chart_categorical():
    df = pd.DataFrame({
        "restaurant_name": ["A", "B", "C", "D", "E"],
        "order_count": [50, 40, 30, 20, 10],
    })
    fig = build_chart(df, _plan("bar"))
    assert fig is not None


def test_horizontal_bar_many_categories():
    df = pd.DataFrame({
        "zone": [f"Zone {i}" for i in range(12)],
        "order_count": list(range(12, 0, -1)),
    })
    fig = build_chart(df, _plan("bar"))
    assert fig is not None


def test_scatter_two_numerics():
    import numpy as np
    rng = __import__("random").Random(42)
    n = 25
    df = pd.DataFrame({
        "avg_rating": [rng.uniform(1, 5) for _ in range(n)],
        "order_count": [rng.randint(10, 200) for _ in range(n)],
    })
    fig = build_chart(df, _plan("scatter"))
    assert fig is not None


def test_empty_df_returns_none():
    df = pd.DataFrame()
    fig = build_chart(df, _plan("bar"))
    assert fig is None


def test_table_fallback_returns_none():
    # Purely text DataFrame has no numeric cols → rule 4 won't match → fallback None
    df = pd.DataFrame({
        "col_a": ["x", "y"],
        "col_b": ["p", "q"],
    })
    fig = build_chart(df, _plan("table"))
    assert fig is None
