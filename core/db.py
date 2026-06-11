import sqlite3
import threading
import pandas as pd
from pathlib import Path
from . import config


class QueryTimeoutError(Exception):
    pass


class QueryError(Exception):
    pass


def _get_conn(path: Path = None) -> sqlite3.Connection:
    db = path or config.DB_PATH
    uri = f"file:{db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(sql: str, db_path: Path = None) -> pd.DataFrame:
    """Execute a read-only SELECT and return a DataFrame. Raises QueryError or QueryTimeoutError."""
    db = db_path or config.DB_PATH
    result_holder = {}
    error_holder  = {}

    def _run():
        conn = None
        try:
            conn = _get_conn(db)
            df = pd.read_sql_query(sql, conn)
            result_holder["df"] = df
        except Exception as e:
            error_holder["err"] = e
        finally:
            if conn:
                conn.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=config.QUERY_TIMEOUT_SEC)

    if t.is_alive():
        conn.interrupt()
        t.join(timeout=1)
        raise QueryTimeoutError(f"Query exceeded {config.QUERY_TIMEOUT_SEC}s timeout")

    if "err" in error_holder:
        raise QueryError(str(error_holder["err"]))

    return result_holder["df"]
