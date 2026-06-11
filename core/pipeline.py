"""Orchestrates: question → guarded SQL → DataFrame → chart spec. Logs every attempt."""
import time
import json
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import plotly.graph_objects as go

from . import config
from .llm import generate, QueryPlan
from .sql_guard import guard, GuardError
from .db import execute_query, QueryError, QueryTimeoutError
from .charts import build_chart


@dataclass
class PipelineResult:
    plan: QueryPlan
    sql: str
    df: pd.DataFrame
    fig: go.Figure | None
    llm_latency: float
    sql_latency: float
    retried: bool
    error: Optional[str] = None


def ask(question: str, model: str = None) -> PipelineResult:
    """Full pipeline. Returns PipelineResult; raises only on unrecoverable guard errors."""
    t_total = time.perf_counter()
    model = model or config.PRIMARY_MODEL
    retried = False
    repair_ctx = None

    plan, llm_lat = generate(question, model=model)

    try:
        safe_sql = guard(plan.sql)
    except GuardError as e:
        _log(question, plan.sql, str(e), llm_lat, 0.0, retried=False, model=model)
        raise

    t_sql = time.perf_counter()
    try:
        df = execute_query(safe_sql)
    except (QueryError, QueryTimeoutError) as e:
        # One retry
        retried = True
        repair_ctx = (plan.sql, str(e))
        plan, llm_lat2 = generate(question, model=model, repair_context=repair_ctx)
        llm_lat += llm_lat2

        try:
            safe_sql = guard(plan.sql)
        except GuardError as e2:
            _log(question, plan.sql, str(e2), llm_lat, 0.0, retried=True, model=model)
            raise

        t_sql = time.perf_counter()
        df = execute_query(safe_sql)

    sql_lat = time.perf_counter() - t_sql

    fig = build_chart(df, plan) if not df.empty else None

    _log(question, safe_sql, None, llm_lat, sql_lat, retried=retried, model=model)

    return PipelineResult(
        plan=plan,
        sql=safe_sql,
        df=df,
        fig=fig,
        llm_latency=llm_lat,
        sql_latency=sql_lat,
        retried=retried,
    )


def _log(question, sql, error, llm_lat, sql_lat, retried, model):
    config.TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "question": question,
        "model": model,
        "sql": sql,
        "error": error,
        "llm_latency": round(llm_lat, 3),
        "sql_latency": round(sql_lat, 3),
        "retried": retried,
    }
    with open(config.TRACE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
