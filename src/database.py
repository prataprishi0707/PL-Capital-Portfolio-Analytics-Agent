import sqlite3
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "portfolio_database.db"

MAX_QUERY_LENGTH = 10_000
MAX_RESULT_ROWS = 100
MAX_SQLITE_OPCODES = 1_000_000

ALLOWED_TABLES = {
    "benchmarks",
    "historical_prices",
    "holdings",
    "portfolio_performance",
    "portfolios",
    "risk_metrics",
    "sectors",
    "securities",
    "transactions",
}

ALLOWED_FUNCTIONS = {
    "abs", "avg", "coalesce", "count", "date", "datetime",
    "dense_rank", "first_value", "ifnull", "julianday",
    "lag", "lead", "length", "lower", "max", "min",
    "nullif", "ntile", "percent_rank", "printf", "rank",
    "replace", "round", "row_number", "rtrim", "strftime",
    "substr", "substring", "sum", "time", "total", "trim",
    "typeof", "upper", "max", "min", "group_concat",
    "json_extract",
}


def get_connection(read_only=True):
    if read_only:
        conn = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro",
            uri=True
        )
        conn.execute("PRAGMA query_only = ON")
        return conn

    return sqlite3.connect(DB_PATH)


def _strip_leading_comments(query):
    normalized = query.lstrip()

    while True:
        if normalized.startswith("--"):
            normalized = normalized.split("\n", 1)[-1].lstrip()

        elif normalized.startswith("/*"):
            if "*/" not in normalized:
                return None
            normalized = normalized.split("*/", 1)[-1].lstrip()

        else:
            return normalized


def _authorizer(action, arg1, arg2, db_name, trigger):
    if action in {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
    }:
        if action == sqlite3.SQLITE_READ:
            return (
                sqlite3.SQLITE_OK
                if arg1 in ALLOWED_TABLES
                else sqlite3.SQLITE_DENY
            )
        return sqlite3.SQLITE_OK

    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (arg2 or arg1 or "").lower()
        return (
            sqlite3.SQLITE_OK
            if function_name in ALLOWED_FUNCTIONS
            else sqlite3.SQLITE_DENY
        )

    return sqlite3.SQLITE_DENY


def validate_sql(query):

    if not isinstance(query, str) or not query.strip():
        return False, "SQL query is empty."

    if len(query) > MAX_QUERY_LENGTH:
        return False, "SQL query exceeds the maximum allowed length."

    normalized = _strip_leading_comments(query)

    if not normalized:
        return False, "Invalid or empty SQL after comments."

    first_word = normalized.split(None, 1)[0].upper()

    if first_word not in ("SELECT", "WITH"):
        return False, "Only SELECT queries are permitted."

    check_query = normalized if normalized.endswith(";") else normalized + ";"

    if not sqlite3.complete_statement(check_query):
        return False, "Incomplete SQL statement."

    conn = None

    try:
        conn = get_connection()
        conn.set_authorizer(_authorizer)
        conn.execute("EXPLAIN " + normalized).fetchall()
        return True, "SQL validation successful."

    except sqlite3.Error as error:
        return False, str(error)

    finally:
        if conn:
            conn.close()


def run_sql_query(query):

    valid, message = validate_sql(query)

    if not valid:
        return {
            "success": False,
            "error": message
        }

    conn = None

    try:
        conn = get_connection()
        conn.set_authorizer(_authorizer)

        opcode_count = 0

        def progress_handler():
            nonlocal opcode_count
            opcode_count += 1
            return int(opcode_count > MAX_SQLITE_OPCODES)

        conn.set_progress_handler(progress_handler, 1000)

        cursor = conn.execute(query)
        columns = [description[0] for description in cursor.description or []]

        raw_rows = cursor.fetchmany(MAX_RESULT_ROWS + 1)
        truncated = len(raw_rows) > MAX_RESULT_ROWS
        raw_rows = raw_rows[:MAX_RESULT_ROWS]

        rows = [
            dict(zip(columns, row))
            for row in raw_rows
        ]

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated
        }

    except sqlite3.Error as error:
        return {
            "success": False,
            "error": str(error)
        }

    finally:
        if conn:
            conn.close()
