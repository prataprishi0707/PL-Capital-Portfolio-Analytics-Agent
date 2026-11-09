
import sys
import sqlite3
import unittest
from pathlib import Path

# Use relative path from this file so tests run in any environment
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from database import run_sql_query, get_connection, validate_sql


class TestSQLSecurity(unittest.TestCase):

    def test_rejects_oversized_query(self):
        valid, message = validate_sql("SELECT 1 " + (" " * 10001))
        self.assertFalse(valid)
        self.assertIn("maximum allowed length", message)

    def test_rejects_unapproved_table(self):
        result = run_sql_query("SELECT * FROM sqlite_master")
        self.assertFalse(result["success"])

    def test_rejects_load_extension(self):
        result = run_sql_query("SELECT load_extension('malicious')")
        self.assertFalse(result["success"])

    def test_limits_results_to_100_rows(self):
        result = run_sql_query(
            "SELECT 1 AS value FROM holdings CROSS JOIN holdings"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["row_count"], 100)
        self.assertTrue(result["truncated"])

    def test_exactly_100_rows_not_truncated(self):
        result = run_sql_query(
            "SELECT 1 AS value FROM holdings "
            "CROSS JOIN holdings LIMIT 100"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["row_count"], 100)
        self.assertFalse(result["truncated"])

    def test_valid_aggregate_functions(self):
        result = run_sql_query(
            "SELECT COUNT(*) AS total, "
            "ROUND(AVG(current_price), 2) AS average_price "
            "FROM securities"
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["rows"][0]["total"], 0)

    def test_valid_window_function(self):
        result = run_sql_query(
            "SELECT portfolio_id, "
            "ROW_NUMBER() OVER (ORDER BY portfolio_id) AS rn "
            "FROM portfolios"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["row_count"], 13)

    def test_read_only_connection(self):
        conn = get_connection()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute(
                    "UPDATE portfolios SET status = 'Inactive'"
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
