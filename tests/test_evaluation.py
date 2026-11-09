"""
Offline evaluation tests — no Gemini API required.
Tests the evaluator's ground-truth SQL execution and exposure comparison logic.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluator import (
    execute_ground_truth_sql,
    compare_results,
    evaluate_exposure,
    load_ground_truth,
)


class TestGroundTruthSQLExecution(unittest.TestCase):
    """Verify that the ground-truth SQL queries return correct results from the real DB."""

    def test_q1_portfolio_count_is_13(self):
        """Q1: COUNT(*) FROM portfolios must return 13."""
        result = execute_ground_truth_sql("SELECT COUNT(*) FROM portfolios;")
        self.assertTrue(result["success"], msg=result.get("error"))
        self.assertEqual(result["row_count"], 1)
        # The column name varies by SQL engine — check the single value
        value = list(result["rows"][0].values())[0]
        self.assertEqual(int(value), 13)

    def test_q2_active_portfolios_returns_list(self):
        """Q2: Active portfolios query must return at least one row."""
        result = execute_ground_truth_sql(
            "SELECT portfolio_name FROM portfolios WHERE status = 'Active';"
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["row_count"], 0)

    def test_q3_technology_sector_securities(self):
        """Q3: Technology sector query must return symbol + company_name rows."""
        result = execute_ground_truth_sql(
            "SELECT s.symbol, s.company_name "
            "FROM securities s "
            "JOIN sectors sec ON s.sector_id = sec.sector_id "
            "WHERE sec.sector_name = 'Technology';"
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["row_count"], 0)
        # Every row must have 'symbol' and 'company_name'
        for row in result["rows"]:
            self.assertIn("symbol", row)
            self.assertIn("company_name", row)


class TestCompareResults(unittest.TestCase):
    """Unit tests for the compare_results() comparator."""

    def test_identical_results_match(self):
        """Identical result dicts must return True."""
        data = {"success": True, "rows": [{"total": 13}]}
        self.assertTrue(compare_results(data, data))

    def test_different_values_do_not_match(self):
        """Different row values must return False."""
        actual = {"success": True, "rows": [{"total": 13}]}
        expected = {"success": True, "rows": [{"total": 12}]}
        self.assertFalse(compare_results(actual, expected))

    def test_different_row_counts_do_not_match(self):
        """Different number of rows must return False."""
        actual = {"success": True, "rows": [{"a": 1}, {"a": 2}]}
        expected = {"success": True, "rows": [{"a": 1}]}
        self.assertFalse(compare_results(actual, expected))

    def test_numeric_tolerance_accepted(self):
        """Values within default abs_tol=1e-4 must match."""
        actual = {"success": True, "rows": [{"val": 13.00009}]}
        expected = {"success": True, "rows": [{"val": 13.0001}]}
        self.assertTrue(compare_results(actual, expected))

    def test_column_name_case_insensitive(self):
        """Column names must be compared case-insensitively."""
        actual = {"success": True, "rows": [{"Total": 13}]}
        expected = {"success": True, "rows": [{"total": 13}]}
        self.assertTrue(compare_results(actual, expected))

    def test_failed_actual_returns_false(self):
        """success=False in actual must return False."""
        actual = {"success": False, "rows": []}
        expected = {"success": True, "rows": [{"total": 13}]}
        self.assertFalse(compare_results(actual, expected))


class TestExposureEvaluator(unittest.TestCase):
    """Verify evaluate_exposure against the actual database."""

    def test_tech_innovation_fund_exposure_passes(self):
        """Q9: evaluate_exposure for Tech Innovation Fund must pass."""
        questions = load_ground_truth()
        q9 = next((q for q in questions if q["id"] == 9), None)
        self.assertIsNotNone(q9, msg="Q9 not found in ground_truth_dataset.json")
        result = evaluate_exposure(q9)
        self.assertTrue(result["success"], msg=result.get("actual", {}).get("error"))
        self.assertTrue(result["passed"],
            msg=f"Exposure mismatch. actual={result.get('actual',{}).get('sector_exposures')} "
                f"expected={result.get('expected')}")

    def test_international_equity_fund_exposure_passes(self):
        """Q10: evaluate_exposure for International Equity Fund must pass."""
        questions = load_ground_truth()
        q10 = next((q for q in questions if q["id"] == 10), None)
        self.assertIsNotNone(q10, msg="Q10 not found in ground_truth_dataset.json")
        result = evaluate_exposure(q10)
        self.assertTrue(result["success"], msg=result.get("actual", {}).get("error"))
        self.assertTrue(result["passed"],
            msg=f"Exposure mismatch. actual={result.get('actual',{}).get('sector_exposures')} "
                f"expected={result.get('expected')}")


if __name__ == "__main__":
    unittest.main()
