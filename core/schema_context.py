"""Builds the schema prompt block: DDL + sample rows + FK map. Called once at startup."""
import sqlite3
from pathlib import Path
from . import config

_CACHE: str | None = None


def get_schema_block(db_path: Path = None) -> str:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _CACHE = _build(db_path or config.DB_PATH)
    return _CACHE


def _build(db_path: Path) -> str:
    ddl = config.SCHEMA_SQL.read_text()

    sample_lines = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    tables = [
        "delivery_zones", "customers", "restaurants", "menu_items",
        "riders", "promotions", "orders", "order_items", "payments", "ratings",
    ]
    for tbl in tables:
        rows = conn.execute(f"SELECT * FROM {tbl} LIMIT 3").fetchall()
        if rows:
            cols = rows[0].keys()
            sample_lines.append(f"/* SELECT * FROM {tbl} LIMIT 3;")
            sample_lines.append("   " + " | ".join(cols))
            for r in rows:
                sample_lines.append("   " + " | ".join(str(r[c]) for c in cols))
            sample_lines.append("*/")
    conn.close()

    return ddl.strip() + "\n\n" + "\n".join(sample_lines)
