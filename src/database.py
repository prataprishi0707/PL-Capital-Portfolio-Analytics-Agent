
import sqlite3
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "portfolio_database.db"


def get_connection(read_only=True):
    if read_only:
        return sqlite3.connect(
            f"file:{DB_PATH}?mode=ro",
            uri=True
        )

    return sqlite3.connect(DB_PATH)


def validate_sql(query):

    if not isinstance(query, str) or not query.strip():
        return False, "SQL query is empty."

    query = query.strip()

    check_query = query if query.endswith(";") else query + ";"

    if not sqlite3.complete_statement(check_query):
        return False, "Incomplete SQL statement."

    normalized = query.lstrip()

    while True:
        if normalized.startswith("--"):
            normalized = normalized.split("\n", 1)[-1].lstrip()

        elif normalized.startswith("/*"):
            if "*/" not in normalized:
                return False, "Unclosed SQL comment."
            normalized = normalized.split("*/", 1)[-1].lstrip()

        else:
            break

    if not normalized:
        return False, "SQL query is empty."

    first_word = normalized.split(None, 1)[0].upper()

    if first_word not in ("SELECT", "WITH"):
        return False, "Only SELECT queries are permitted."

    conn = get_connection()

    def authorizer(action, arg1, arg2, db_name, trigger):
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION
        }

        return (
            sqlite3.SQLITE_OK
            if action in allowed
            else sqlite3.SQLITE_DENY
        )

    try:
        conn.set_authorizer(authorizer)
        conn.execute("EXPLAIN " + query).fetchall()
        return True, "SQL validation successful."

    except Exception as e:
        return False, str(e)

    finally:
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

        def restrict_operations(action, arg1, arg2, db_name, trigger):
            allowed = {
                sqlite3.SQLITE_SELECT,
                sqlite3.SQLITE_READ,
                sqlite3.SQLITE_FUNCTION
            }

            return (
                sqlite3.SQLITE_OK
                if action in allowed
                else sqlite3.SQLITE_DENY
            )

        conn.set_authorizer(restrict_operations)

        result = pd.read_sql_query(query, conn)

        return {
            "success": True,
            "columns": result.columns.tolist(),
            "rows": result.to_dict(orient="records"),
            "row_count": len(result)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        if conn:
            conn.close()
