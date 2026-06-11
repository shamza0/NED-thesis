"""Ollama client: structured output call + execution-guided retry loop."""
import time
import json
from typing import Optional
from pydantic import BaseModel
from typing import Literal
import ollama

from . import config
from .prompts import build_system_prompt, build_few_shot_messages


class QueryPlan(BaseModel):
    reasoning: str
    sql: str
    chart_hint: Literal["bar", "line", "pie", "scatter", "table", "stat"]
    title: str


_SYSTEM_PROMPT: str | None = None
_FEW_SHOT: list | None = None


def _get_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = build_system_prompt()
    return _SYSTEM_PROMPT


def _get_few_shot() -> list:
    global _FEW_SHOT
    if _FEW_SHOT is None:
        _FEW_SHOT = build_few_shot_messages()
    return _FEW_SHOT


def _call_llm(messages: list[dict], model: str) -> tuple[QueryPlan, float]:
    t0 = time.perf_counter()
    resp = ollama.chat(
        model=model,
        messages=messages,
        format=QueryPlan.model_json_schema(),
        options={
            "temperature": config.TEMPERATURE,
            "num_ctx": config.NUM_CTX,
            "keep_alive": config.KEEP_ALIVE,
        },
    )
    latency = time.perf_counter() - t0
    plan = QueryPlan.model_validate_json(resp["message"]["content"])
    return plan, latency


def generate(
    question: str,
    model: str = None,
    repair_context: Optional[tuple[str, str]] = None,
) -> tuple[QueryPlan, float]:
    """Generate a QueryPlan. If repair_context=(bad_sql, error_msg), appends a repair prompt."""
    model = model or config.PRIMARY_MODEL
    system = _get_system_prompt()
    few_shot = _get_few_shot()

    messages = [{"role": "system", "content": system}] + few_shot

    if repair_context:
        bad_sql, err_msg = repair_context
        repair_note = (
            f"Your previous query failed.\n"
            f"Query: {bad_sql}\n"
            f"SQLite error: {err_msg}\n"
            f"Return a corrected query."
        )
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": json.dumps({"reasoning": "", "sql": bad_sql, "chart_hint": "table", "title": ""})})
        messages.append({"role": "user", "content": repair_note})
    else:
        messages.append({"role": "user", "content": question})

    return _call_llm(messages, model)


def prewarm(model: str = None):
    """Send a trivial query to load the model into memory before first user request."""
    model = model or config.PRIMARY_MODEL
    try:
        ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            options={"keep_alive": config.KEEP_ALIVE, "num_ctx": 128},
        )
    except Exception:
        pass
