"""Rule-based chart selection + Plotly figure builder."""
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import QueryPlan

MONEY_KEYWORDS = {"revenue", "amount", "price", "total", "sales", "income", "earning"}


def _prettify(col: str) -> str:
    return col.replace("_", " ").title()


def _is_money_col(col: str) -> bool:
    return any(k in col.lower() for k in MONEY_KEYWORDS)


def _format_money(val):
    return f"PKR {val:,.0f}"


def _is_temporal(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    # Detect YYYY-MM or YYYY-MM-DD strings
    if pd.api.types.is_object_dtype(series):
        sample = series.dropna().head(5)
        return all(bool(re.match(r"^\d{4}-\d{2}", str(v))) for v in sample)
    return False


def build_chart(df: pd.DataFrame, plan: "QueryPlan") -> go.Figure | None:
    if df is None or df.empty:
        return None

    hint = plan.chart_hint
    title = plan.title
    cols = df.columns.tolist()
    ncols = len(cols)

    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]
    temp_cols = [c for c in cols if _is_temporal(df[c])]

    override_logged = False

    # Rule 1: 1 row × 1 numeric → stat
    if len(df) == 1 and len(num_cols) == 1:
        val = df[num_cols[0]].iloc[0]
        fig = go.Figure(go.Indicator(
            mode="number",
            value=val,
            title={"text": title},
            number={"prefix": "PKR " if _is_money_col(num_cols[0]) else ""},
        ))
        return fig

    # Rule 2: temporal + numeric → line
    if temp_cols and num_cols:
        t_col = temp_cols[0]
        y_cols = num_cols
        series_col = cat_cols[0] if len(cat_cols) == 1 and cat_cols[0] != t_col else None
        if series_col:
            fig = px.line(df, x=t_col, y=y_cols[0], color=series_col,
                          title=title, labels={c: _prettify(c) for c in cols})
        else:
            fig = px.line(df, x=t_col, y=y_cols[0],
                          title=title, labels={c: _prettify(c) for c in cols})
        if hint != "line":
            override_logged = True
        return fig

    # Rule 3: categorical + numeric, ≤6 rows, non-negative, hint pie → pie
    if cat_cols and num_cols and len(df) <= 6 and (df[num_cols[0]] >= 0).all() and hint == "pie":
        fig = px.pie(df, names=cat_cols[0], values=num_cols[0], title=title)
        return fig

    # Rule 4: categorical + numeric → bar
    if cat_cols and num_cols:
        orientation = "h" if len(df) > 8 else "v"
        sort_df = df.sort_values(num_cols[0], ascending=(orientation == "h"))
        if orientation == "h":
            fig = px.bar(sort_df, x=num_cols[0], y=cat_cols[0], orientation="h",
                         title=title, labels={c: _prettify(c) for c in cols})
        else:
            fig = px.bar(sort_df, x=cat_cols[0], y=num_cols[0],
                         title=title, labels={c: _prettify(c) for c in cols})
        if hint not in ("bar", "pie"):
            override_logged = True
        return fig

    # Rule 5: two numeric columns, >20 rows → scatter
    if len(num_cols) >= 2 and len(df) > 20:
        fig = px.scatter(df, x=num_cols[0], y=num_cols[1],
                         title=title, labels={c: _prettify(c) for c in cols})
        if hint != "scatter":
            override_logged = True
        return fig

    # Rule 6: fallback → table
    return None  # caller uses st.dataframe
