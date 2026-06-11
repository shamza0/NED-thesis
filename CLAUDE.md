# VizQuery — Claude Code Guide

## What this project is
MS thesis prototype (NED University, CT-5002). A locally-running text-to-SQL + chart system.
Pipeline: natural-language question → Ollama LLM → SQL → SQLite → Plotly chart in Streamlit.

## Setup (first time)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
python data/generate_data.py
```

## Run
```bash
ollama serve                      # terminal 1 — keep running
streamlit run app.py              # terminal 2
pytest                            # run tests
python eval/run_eval.py           # run evaluation harness
```

## Hard constraints — never violate
- 100% local. No cloud APIs of any kind.
- `core/` must never import Streamlit (speech module bolts on next semester).
- Synthetic data only (ethics requirement).
- DB seed is 42 — generator must stay fully reproducible.

## Architecture
```
app.py                  Streamlit UI — thin wrapper only
core/config.py          model names, paths, limits
core/db.py              read-only SQLite execution (5s timeout, threaded)
core/schema_context.py  builds schema prompt block once at startup
core/prompts.py         system prompt + 4 few-shot pairs
core/llm.py             Ollama structured-output call + 1-retry loop
core/sql_guard.py       SELECT-only enforcement, hallucination detection, LIMIT injection
core/charts.py          rule-based chart selection (rules beat LLM hint on conflict)
core/pipeline.py        orchestrates everything + writes trace.jsonl
eval/run_eval.py        execution-accuracy harness, outputs CSV per model
```

## Key design decisions
- **Single LLM call** returns `QueryPlan` (reasoning + sql + chart_hint + title) via Ollama structured output (`format=` constrained decoding). No regex parsing.
- `reasoning` field first = lightweight chain-of-thought before SQL writing.
- `temperature=0` + `seed=42` everywhere = reproducible eval numbers.
- `keep_alive=30m` keeps model in RAM — warm latency <2s vs ~100s cold.
- Execution accuracy metric (not string match): predicted SQL is correct iff result set matches gold.

## Models
| Model | Role |
|---|---|
| `qwen2.5-coder:7b` | Primary (best small-model SQL) |
| `llama3.1:8b` | Comparison (M7) |
| `phi3.5` | Comparison (M7) |

## Milestones status
- M1 Data ✅ — 30k orders, all assertions pass
- M2 Guard + DB ✅ — 28/28 tests green
- M3 LLM core ✅ — 10/10 smoke questions pass
- M4 Charts ✅ — all chart shape tests green
- M5 UI ✅ — all 6 sidebar examples produce correct chart type
- M6 Eval — running
- M7 Comparison models — pending (needs llama3.1:8b + phi3.5 pulled)

## Eval
```bash
python eval/run_eval.py --model qwen2.5-coder:7b   # M6
python eval/run_eval.py --all-models                # M7
```
Results land in `eval/results/`. Trace log at `eval/results/trace.jsonl`.

## Acceptance targets (from thesis proposal)
- Guard blocks 100% of non-SELECT in tests ✅
- Execution accuracy ≥ 80% easy, ≥ 60% medium (qwen2.5-coder:7b + retry)
- Warm p50 latency < 6s end-to-end
- All 6 sidebar examples → correct chart type ✅
