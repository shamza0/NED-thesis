"""Evaluation harness: execution accuracy across models and retry settings."""
import json
import csv
import time
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import config
from core.llm import generate
from core.sql_guard import guard, GuardError, HallucinationError
from core.db import execute_query, QueryError, QueryTimeoutError

GOLD_PATH = Path(__file__).parent / "gold_questions.json"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def _sets_equal(df_pred, df_gold, tol=1e-6):
    """Execution accuracy: result sets equal as sorted multisets, column-order ignored."""
    if df_pred is None or df_gold is None:
        return False
    if df_pred.shape[0] != df_gold.shape[0]:
        return False

    def rows(df):
        out = []
        for _, row in df.iterrows():
            r = []
            for v in row.values:
                try:
                    r.append(round(float(v), 6))
                except (TypeError, ValueError):
                    r.append(str(v).strip().lower())
            out.append(tuple(sorted(r, key=str)))
        return sorted(out, key=str)

    return rows(df_pred) == rows(df_gold)


def run_eval(model: str, use_retry: bool):
    questions = json.loads(GOLD_PATH.read_text())
    tag = f"{model.replace(':', '_').replace('.', '_')}_{'retry' if use_retry else 'noretry'}"
    trace_path = RESULTS_DIR / f"{tag}_trace.jsonl"
    csv_path   = RESULTS_DIR / f"{tag}.csv"

    stats = {
        "correct": 0, "total": 0,
        "guard_blocked": 0, "hallucinated": 0,
        "retry_attempted": 0, "retry_success": 0,
        "latencies": [],
        "by_difficulty": {"easy": {"c": 0, "t": 0}, "medium": {"c": 0, "t": 0}, "hard": {"c": 0, "t": 0}},
    }

    gold_cache = {}
    for q in questions:
        try:
            gold_cache[q["id"]] = execute_query(q["gold_sql"])
        except Exception:
            gold_cache[q["id"]] = None

    rows = []
    for q in questions:
        qid      = q["id"]
        question = q["question"]
        diff     = q["difficulty"]
        t0       = time.perf_counter()
        retried  = False
        correct  = False
        blocked  = False
        halluc   = False
        error_msg = None

        try:
            plan, _ = generate(question, model=model)
            try:
                safe_sql = guard(plan.sql)
            except HallucinationError as e:
                halluc = True
                raise GuardError(str(e)) from e

            try:
                df_pred = execute_query(safe_sql)
            except (QueryError, QueryTimeoutError) as e:
                if use_retry:
                    stats["retry_attempted"] += 1
                    retried = True
                    plan2, _ = generate(question, model=model, repair_context=(plan.sql, str(e)))
                    safe_sql = guard(plan2.sql)
                    df_pred  = execute_query(safe_sql)
                    plan = plan2
                    stats["retry_success"] += 1
                else:
                    raise

            df_gold = gold_cache.get(qid)
            correct = _sets_equal(df_pred, df_gold)

        except GuardError:
            blocked = True
            error_msg = "guard_blocked"
        except Exception as e:
            error_msg = str(e)

        latency = time.perf_counter() - t0
        stats["total"] += 1
        stats["by_difficulty"][diff]["t"] += 1
        if correct:
            stats["correct"] += 1
            stats["by_difficulty"][diff]["c"] += 1
        if blocked:
            stats["guard_blocked"] += 1
        if halluc:
            stats["hallucinated"] += 1
        stats["latencies"].append(latency)

        row = {
            "id": qid, "difficulty": diff, "correct": correct,
            "retried": retried, "blocked": blocked,
            "hallucinated": halluc, "latency": round(latency, 3),
            "error": error_msg,
        }
        rows.append(row)

        with open(trace_path, "a") as f:
            f.write(json.dumps(row) + "\n")

        print(f"  [{qid:>2}] {diff:6} {'✓' if correct else '✗'}  {latency:.1f}s  {question[:55]}")

    # Write CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    lats = sorted(stats["latencies"])
    p50  = lats[len(lats) // 2]
    p95  = lats[int(len(lats) * 0.95)]

    summary = {
        "model": model, "retry": use_retry,
        "accuracy_overall": round(stats["correct"] / stats["total"], 3),
        "accuracy_easy":   round(stats["by_difficulty"]["easy"]["c"]   / max(1, stats["by_difficulty"]["easy"]["t"]), 3),
        "accuracy_medium": round(stats["by_difficulty"]["medium"]["c"] / max(1, stats["by_difficulty"]["medium"]["t"]), 3),
        "accuracy_hard":   round(stats["by_difficulty"]["hard"]["c"]   / max(1, stats["by_difficulty"]["hard"]["t"]), 3),
        "guard_block_rate": round(stats["guard_blocked"] / stats["total"], 3),
        "hallucination_rate": round(stats["hallucinated"] / stats["total"], 3),
        "retry_success_rate": round(stats["retry_success"] / max(1, stats["retry_attempted"]), 3),
        "p50_latency": round(p50, 2),
        "p95_latency": round(p95, 2),
    }

    print(f"\n  === {model} retry={use_retry} ===")
    for k, v in summary.items():
        print(f"    {k:<25} {v}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=config.PRIMARY_MODEL)
    parser.add_argument("--all-models", action="store_true")
    args = parser.parse_args()

    models = config.ALL_MODELS if args.all_models else [args.model]
    all_summaries = []
    for m in models:
        for retry in [False, True]:
            s = run_eval(m, retry)
            all_summaries.append(s)

    print("\n=== COMBINED RESULTS ===")
    hdrs = list(all_summaries[0].keys())
    print("  " + "  ".join(f"{h:<22}" for h in hdrs))
    for s in all_summaries:
        print("  " + "  ".join(f"{str(s[h]):<22}" for h in hdrs))
