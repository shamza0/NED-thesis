from pathlib import Path

DB_PATH    = Path(__file__).parent.parent / "data" / "foodpanda_lite.db"
SCHEMA_SQL = Path(__file__).parent.parent / "data" / "schema.sql"
TRACE_LOG  = Path(__file__).parent.parent / "eval" / "results" / "trace.jsonl"

PRIMARY_MODEL    = "qwen2.5-coder:7b"
COMPARISON_MODELS = ["llama3.1:8b", "phi3.5"]
ALL_MODELS       = [PRIMARY_MODEL] + COMPARISON_MODELS

OLLAMA_HOST  = "http://localhost:11434"
TEMPERATURE  = 0
NUM_CTX      = 8192
KEEP_ALIVE   = "30m"

QUERY_TIMEOUT_SEC = 5
MAX_ROWS          = 100
