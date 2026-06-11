# Solution Spec: Text-Driven Data Visualization System Using a Private LLM
**Project codename:** `vizquery` · **Target:** MS Thesis prototype (CT-5002, NED University)
**This document is the build instruction set for Claude Code. Follow milestones in order.**

---

## 1. What We're Building

A locally-running system where a user types a natural-language question about a food-delivery
database and receives an automatically generated chart. Pipeline:

```
Text question → Private LLM (Ollama) → SQL → SQLite → Result → Rule-based chart selection → Plotly chart
```

**Hard constraints (from thesis proposal — do not violate):**
- 100% local & open-source. No cloud APIs of any kind.
- Synthetic data only (ethics requirement).
- ~10 tables, ~10k records in major tables, simple relational structure.
- Must be evaluable on: SQL accuracy, usability, response latency.

**Out of scope for now:** speech input (next semester — but architecture must allow a
transcription layer to bolt on in front of the text input without refactoring).

**Target machine:** MacBook Pro M1, 16GB RAM, Ollama already installed.

---

## 2. Tech Stack (fixed — do not substitute)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | ecosystem |
| Database | SQLite (file: `data/foodpanda_lite.db`) | zero-config, sufficient for 100k rows |
| Data generation | Faker (seeded, `seed=42`) | reproducible synthetic data, ethics-compliant |
| LLM runtime | Ollama (localhost:11434) via `ollama` Python package | already installed |
| Primary model | `qwen2.5-coder:7b` | best small-model SQL performance |
| Comparison models | `llama3.1:8b`, `phi3.5` | for thesis model-comparison results section |
| LLM output | Ollama **structured outputs** (`format=` + Pydantic schema) | guaranteed parseable JSON, no regex scraping |
| SQL validation | `sqlglot` (parse/inspect) + custom guard | read-only enforcement |
| Charts | Plotly | interactive, Streamlit-native |
| UI | Streamlit | fastest path to a polished demo |
| Testing/eval | pytest + custom eval harness | execution-accuracy measurement |

---

## 3. Repository Structure

```
vizquery/
├── SPEC.md                  (this file)
├── requirements.txt
├── README.md                (setup + run instructions)
├── data/
│   ├── generate_data.py     (Faker-based generator, seeded)
│   ├── schema.sql           (DDL — single source of truth)
│   └── foodpanda_lite.db    (generated artifact, gitignored)
├── core/                    (pure Python, NO streamlit imports here)
│   ├── __init__.py
│   ├── config.py            (model names, paths, limits, temperature)
│   ├── db.py                (connection, read-only query execution, timeout)
│   ├── schema_context.py    (builds the schema prompt block: DDL + sample rows + FK map)
│   ├── llm.py               (Ollama client, structured-output call, retry loop)
│   ├── prompts.py           (system prompt, few-shot examples — see §6)
│   ├── sql_guard.py         (validation: SELECT-only, LIMIT injection, denylist)
│   ├── pipeline.py          (orchestrates: question → guarded SQL → result → chart spec)
│   └── charts.py            (rule-based chart selection + plotly figure builder)
├── eval/
│   ├── gold_questions.json  (50 questions w/ gold SQL, difficulty-tagged)
│   ├── run_eval.py          (execution-accuracy harness, per-model, CSV output)
│   └── results/             (gitignored)
├── app.py                   (Streamlit UI — thin layer over core.pipeline)
└── tests/
    ├── test_sql_guard.py
    ├── test_charts.py
    └── test_pipeline.py
```

**Design rule:** `core/` must never import Streamlit. Next semester's speech module will call
`core.pipeline.ask(question_text)` exactly as `app.py` does.

---

## 4. Data Layer

### 4.1 Schema (`data/schema.sql`)

Ten tables, Karachi-themed food delivery platform ("Foodpanda-lite"):

```sql
CREATE TABLE delivery_zones (
    id INTEGER PRIMARY KEY,
    city TEXT NOT NULL,              -- 'Karachi'
    zone_name TEXT NOT NULL          -- 'Clifton', 'Gulshan-e-Iqbal', 'DHA', 'Saddar', ...
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id),
    signup_date DATE NOT NULL
);

CREATE TABLE restaurants (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine_type TEXT NOT NULL,      -- 'Biryani', 'BBQ', 'Pizza', 'Chinese', 'Fast Food', 'Desi', 'Dessert'
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id),
    rating REAL                      -- 1.0–5.0
);

CREATE TABLE menu_items (
    id INTEGER PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,          -- 'Main', 'Starter', 'Drink', 'Dessert'
    price REAL NOT NULL
);

CREATE TABLE riders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    zone_id INTEGER NOT NULL REFERENCES delivery_zones(id),
    vehicle_type TEXT NOT NULL,      -- 'Bike', 'Car', 'Bicycle'
    joined_date DATE NOT NULL
);

CREATE TABLE promotions (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    discount_pct REAL NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    rider_id INTEGER REFERENCES riders(id),
    promo_id INTEGER REFERENCES promotions(id),  -- nullable, ~15% of orders
    order_time TIMESTAMP NOT NULL,
    delivered_time TIMESTAMP,                    -- NULL if cancelled
    status TEXT NOT NULL,            -- 'delivered', 'cancelled', 'in_progress'
    total_amount REAL NOT NULL       -- PKR
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    quantity INTEGER NOT NULL,
    item_price REAL NOT NULL,
    PRIMARY KEY (order_id, menu_item_id)
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    method TEXT NOT NULL,            -- 'cash', 'card', 'easypaisa', 'jazzcash'
    amount REAL NOT NULL,
    status TEXT NOT NULL             -- 'completed', 'refunded', 'failed'
);

CREATE TABLE ratings (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    food_rating INTEGER NOT NULL,    -- 1–5
    delivery_rating INTEGER NOT NULL -- 1–5
);
```

### 4.2 Data generation (`data/generate_data.py`)

- `Faker` with `Faker.seed(42)` and `random.seed(42)` — **fully reproducible**.
- Volumes: 12 zones · 8,000 customers · 400 restaurants · ~4,000 menu_items ·
  600 riders · 20 promotions · **30,000 orders** · ~70,000 order_items ·
  30,000 payments · ~18,000 ratings (60% of delivered orders rated).
- Realism rules (important — these make demo answers look sane):
  - `order_time` spread over the last 18 months with a mild upward trend and
    weekend peaks (Fri/Sat/Sun ×1.5 weight).
  - `delivered_time = order_time + N(35, 12) minutes`, clamped 12–120; higher mean for
    far zones to create a real "slowest zone" answer.
  - ~6% cancelled orders (delivered_time NULL).
  - Pakistani names via `Faker('en_PK')` if available, else curated name lists.
  - Dish names from curated lists per cuisine (e.g. 'Chicken Biryani', 'Seekh Kebab',
    'Margherita Pizza') — NOT faker.word().
  - `total_amount` = sum of its order_items minus promo discount (consistency check in generator).
- Generator ends with assertion checks (row counts, FK integrity, totals reconcile) and
  prints a summary table.

---

## 5. LLM Layer — the core of the thesis

### 5.1 Single-call structured output (NOT chatty prompting)

We make **one** LLM call per question. The model is *constrained* (Ollama `format=` parameter,
which uses grammar-based constrained decoding) to return JSON matching this Pydantic model:

```python
from pydantic import BaseModel
from typing import Literal, Optional

class QueryPlan(BaseModel):
    reasoning: str               # 1-2 sentence plan: tables needed, joins, aggregation
    sql: str                     # a single SQLite SELECT statement
    chart_hint: Literal["bar", "line", "pie", "scatter", "table", "stat"]
    title: str                   # human-readable chart title
```

Call shape:

```python
import ollama
resp = ollama.chat(
    model=cfg.model,
    messages=[{"role": "system", "content": SYSTEM_PROMPT},
              *FEW_SHOT_MESSAGES,
              {"role": "user", "content": user_question}],
    format=QueryPlan.model_json_schema(),
    options={"temperature": 0, "num_ctx": 8192, "keep_alive": "30m"},
)
plan = QueryPlan.model_validate_json(resp["message"]["content"])
```

Why this design (state this in thesis):
- `reasoning` field first = lightweight chain-of-thought; the model plans joins before
  writing SQL, which measurably reduces join errors in small models.
- Constrained decoding guarantees parseable output — no markdown fences, no chatter.
- `temperature: 0` → deterministic, reproducible eval numbers.
- `keep_alive: 30m` keeps the model in memory → first-token latency drops from
  ~8s (cold load) to <1s on subsequent queries. Critical for the latency eval.
- `chart_hint` comes free in the same call (no second LLM round-trip = faster).

### 5.2 System prompt (`core/prompts.py`)

Structure (assemble programmatically from `schema_context.py`, never hand-paste schema):

```
You are an expert SQLite analyst for a food delivery platform in Karachi, Pakistan.
Convert the user's question into ONE valid SQLite SELECT query.

DATABASE SCHEMA:
<full CREATE TABLE DDL, verbatim from schema.sql>

SAMPLE ROWS (so you know real value formats):
<3 rows per table, rendered as: /* SELECT * FROM orders LIMIT 3; ... */>

RULES:
- SQLite dialect only. Use strftime() for date manipulation (e.g. strftime('%Y-%m', order_time)).
- Only SELECT statements. Never modify data.
- status values are lowercase: 'delivered', 'cancelled', 'in_progress'.
- Currency is PKR. Delivery duration in minutes =
  (julianday(delivered_time) - julianday(order_time)) * 24 * 60.
- Always alias aggregate columns with readable names (e.g. AS total_revenue).
- For time series, GROUP BY a strftime() bucket and ORDER BY it ascending.
- LIMIT results to 100 rows unless the question implies a top-N (then use that N).
- chart_hint guide: time series → line; category comparison → bar;
  share-of-whole with ≤6 categories → pie; two numeric measures → scatter;
  single number → stat; anything else → table.
```

**Why DDL + sample rows:** research on text-to-SQL prompting shows the CREATE TABLE
representation with foreign keys, plus a few sample rows exposing real value formats,
is the strongest-performing schema encoding for prompted (non-finetuned) models.
Total schema block ≈ 1,800 tokens — fits easily in 8k context with room for few-shots.

### 5.3 Few-shot examples (`core/prompts.py`)

Exactly **4 few-shot pairs** as prior user/assistant message turns (assistant turns are
serialized QueryPlan JSON, so the model sees the exact output format). Cover the four
archetypes:

1. Time series + join: "Show monthly revenue for the last 6 months" → line
2. Top-N aggregation: "Top 5 restaurants by number of orders" → bar
3. Share-of-whole: "Split of payment methods" → pie
4. Computed metric + filter: "Average delivery time by zone for delivered orders" → bar

(Static few-shots are sufficient at this scale. Embedding-based dynamic example
retrieval is a documented stretch goal — see §10.)

### 5.4 Execution-guided retry loop (`core/llm.py`)

```
plan = generate(question)
sql  = guard(plan.sql)                 # §5.5 — may raise GuardError
try:
    df = execute(sql)                  # read-only, 5s timeout
except SQLError as e:
    plan = generate(question, repair_context=(plan.sql, str(e)))   # ONE retry
    sql  = guard(plan.sql)
    df   = execute(sql)
```

- Repair prompt appends: "Your previous query failed. Query: <sql>. SQLite error: <error>.
  Return a corrected query."
- **Max 1 retry** (keeps worst-case latency bounded; also gives the thesis a clean
  ablation: accuracy with retry ON vs OFF).
- Empty result set (0 rows) is NOT retried — it's shown to the user as "no data matched,"
  because empty ≠ wrong.
- Log every attempt (question, sql, error, latency, retried?) to `eval/results/trace.jsonl` —
  this log IS the thesis evidence.

### 5.5 SQL guard (`core/sql_guard.py`)

Defense-in-depth, all checks must pass:

1. Parse with `sqlglot` (dialect="sqlite"). Parse failure → GuardError.
2. Exactly one statement; statement type must be SELECT (CTEs allowed if they end in SELECT).
3. Denylist tokens anywhere: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, PRAGMA,
   REPLACE, TRUNCATE, VACUUM.
4. Referenced tables/columns must exist in the schema (sqlglot can extract identifiers;
   catches hallucinated columns BEFORE execution — log these separately, it's a thesis metric:
   "hallucination rate").
5. If no LIMIT present and no aggregate-only result, inject `LIMIT 100`.
6. Execute on a connection opened with `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`
   (read-only at the engine level) + 5-second interrupt timer.

---

## 6. Chart Selection (`core/charts.py`)

Rule-based, deterministic, with the LLM's `chart_hint` as a tiebreaker — rules win on conflict
(log conflicts; "% of chart hints overridden" is a thesis stat).

Decision order on the result DataFrame:

1. 1 row × 1 numeric col → **stat card** (big number, st.metric)
2. Has a temporal column (parseable dates / 'YYYY-MM' strings) + numeric → **line**
   (multi-series if a third categorical col exists)
3. Categorical + numeric, ≤6 rows, values ≥0, hint == "pie" → **pie**
4. Categorical + numeric → **bar** (horizontal if >8 categories; sorted desc unless temporal)
5. Two numeric columns, >20 rows → **scatter**
6. Fallback → **table** (st.dataframe)

Every chart gets: title from `plan.title`, axis labels from SQL column aliases
(prettified: `total_revenue` → "Total Revenue"), PKR formatting on money columns.

---

## 7. Streamlit UI (`app.py`)

Single page, in order:
- Header + model selector (dropdown: qwen2.5-coder:7b / llama3.1:8b / phi3.5) — lets the
  demo show model comparison live.
- `st.chat_input` for the question (chat-style history above it).
- Per answer, render: the chart (or stat/table) → an expander "View SQL" showing the
  generated SQL (syntax-highlighted) + the reasoning + latency breakdown
  (LLM time / SQL time / total).
- Sidebar: 6 example-question buttons (one per chart type) that fill the input — crucial
  for demos and usability testing.
- Errors are friendly: GuardError → "I generated an unsafe/invalid query, try rephrasing";
  retry-exhausted → show the SQL error in the expander.

No auth, no multi-user state, no backend server. `core/` stays import-clean for the
future speech module.

---

## 8. Evaluation Harness (`eval/`)

This section is what gets the thesis marks. Build it properly.

### 8.1 Gold question set (`eval/gold_questions.json`)

50 questions, hand-written, each: `{id, question, gold_sql, difficulty, expected_chart}`.
Difficulty distribution: 20 easy (single table), 20 medium (1 join or strftime bucket),
10 hard (2+ joins, subquery, or computed metric like delivery duration).

### 8.2 Metric: **Execution Accuracy** (standard in Spider/BIRD benchmarks)

Predicted SQL is correct iff its executed result set matches the gold SQL's result set
(compare as sorted sets of rows, float tolerance 1e-6, column order ignored).
NOT string-matching the SQL — different SQL producing identical results counts as correct.

### 8.3 Harness (`eval/run_eval.py`)

For each model × {retry ON, retry OFF}:
- run all 50 questions, record: execution_accuracy, guard_block_rate, hallucinated_column_rate,
  retry_success_rate, chart_hint_agreement, p50/p95 latency.
- Output: `eval/results/<model>_<config>.csv` + a printed summary table.
- Everything seeded/temp-0 → rerunnable, same numbers.

This yields the thesis's headline results table:
*Model × (Easy/Medium/Hard accuracy) × Latency* — plus the retry ablation.

---

## 9. Performance Requirements

- Warm end-to-end latency (question → chart): **p50 < 6s, p95 < 15s** on M1 16GB.
- Achieved via: keep_alive=30m (no model reload), single LLM call, num_ctx=8192 (not larger),
  schema block pre-built once at startup (not per request), SQLite indices on all FK columns
  + orders(order_time), orders(status).
- App startup: pre-warm the model with a trivial call so the first user query isn't cold.

## 10. Stretch Goals (only after Milestone 6 passes)

- Dynamic few-shot retrieval: embed gold questions (sentence-transformers, local),
  pick 3 nearest examples per query.
- Follow-up questions using chat history (pass prior Q+SQL as context).
- "Explain this chart" button (second LLM call summarizing the result in plain English).

---

## 11. Build Milestones (Claude Code: execute in order, each ends with passing tests)

1. **M1 — Data:** schema.sql + generate_data.py + integrity assertions. ✓ when DB builds
   reproducibly and spot-check queries return sane values.
2. **M2 — Guard + DB:** sql_guard.py + db.py + tests (malicious SQL blocked, hallucinated
   column caught, LIMIT injected, read-only enforced).
3. **M3 — LLM core:** schema_context.py + prompts.py + llm.py with structured output +
   retry loop. ✓ when 10 smoke-test questions return valid QueryPlan JSON.
4. **M4 — Charts:** charts.py rules + tests on synthetic DataFrames of each shape.
5. **M5 — UI:** app.py wired to core.pipeline. ✓ when all 6 sidebar examples render correct
   chart types end-to-end.
6. **M6 — Eval:** gold_questions.json (50) + run_eval.py. ✓ when full eval runs for
   qwen2.5-coder:7b and produces the results CSV.
7. **M7 — Comparison:** run eval for llama3.1:8b + phi3.5; produce combined results table.

## 12. Acceptance Criteria

- [ ] `python data/generate_data.py` builds the DB from scratch, reproducibly (seed 42).
- [ ] `pytest` green.
- [ ] Guard blocks 100% of non-SELECT statements in tests.
- [ ] Execution accuracy ≥ 80% on easy, ≥ 60% on medium questions with qwen2.5-coder:7b + retry.
- [ ] Warm p50 latency < 6s end-to-end.
- [ ] Streamlit demo: all 6 example questions produce the expected chart type.
- [ ] Eval CSVs exist for 3 models; trace.jsonl logging works.
