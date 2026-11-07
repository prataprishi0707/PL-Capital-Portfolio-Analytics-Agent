import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from database import run_sql_query
from exposure_calculator import calculate_sector_exposure
from portfolio_health import analyze_portfolio_health
from portfolio_comparison import compare_portfolios
from risk_analyzer import analyze_portfolio_risk


class TestPortfolioBackend(unittest.TestCase):

    def test_sql_query_returns_correct_portfolio_count(self):
        result = run_sql_query(
            "SELECT COUNT(*) AS total FROM portfolios"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["rows"][0]["total"], 13)

    def test_sql_rejects_delete_query(self):
        result = run_sql_query(
            "DELETE FROM portfolios"
        )

        self.assertFalse(result["success"])
        self.assertIn("SELECT", result["error"])

    def test_exposure_calculator_excludes_bonds(self):
        result = calculate_sector_exposure(
            "Tech Innovation Fund"
        )

        self.assertTrue(result["success"])
        self.assertAlmostEqual(
            result["total_equity_exposure"], 100.0
        )

        self.assertEqual(len(result["sector_exposures"]), 1)
        self.assertEqual(
            result["sector_exposures"][0]["sector_name"],
            "Technology"
        )

        self.assertAlmostEqual(
            result["sector_exposures"][0]["exposure_percentage"],
            100.0
        )

    def test_portfolio_health_allocation(self):
        result = analyze_portfolio_health(
            "Balanced Portfolio"
        )

        self.assertTrue(result["success"])
        self.assertAlmostEqual(
            result["total_stock_allocation"], 36.0
        )
        self.assertAlmostEqual(
            result["total_bond_allocation"], 64.0
        )
        self.assertAlmostEqual(
            result["total_recorded_allocation"], 100.0
        )
        self.assertAlmostEqual(
            result["unallocated_allocation"], 0.0
        )

    def test_portfolio_comparison(self):
        result = compare_portfolios(
            "Tech Innovation Fund",
            "Growth Equity Fund"
        )

        self.assertTrue(result["success"])

        self.assertEqual(
            result["portfolio_1"],
            "Tech Innovation Fund"
        )
        self.assertEqual(
            result["portfolio_2"],
            "Growth Equity Fund"
        )

        metrics = result["performance_and_risk"]

        self.assertAlmostEqual(
            metrics["total_return_1y"]["difference"],
            20.5
        )
        self.assertAlmostEqual(
            metrics["beta"]["difference"],
            0.35
        )

        quality = result["data_quality"]

        self.assertEqual(
            quality["portfolio_1"]["analysis_status"],
            "full"
        )
        self.assertAlmostEqual(
            quality["portfolio_1"]["unallocated_allocation"],
            0.0
        )

    def test_risk_analyzer(self):
        result = analyze_portfolio_risk(
            "Tech Innovation Fund"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["risk_level"], "high")

        self.assertEqual(
            len(result["available_metrics"]), 9
        )
        self.assertEqual(
            len(result["unavailable_metrics"]), 0
        )


    def test_unknown_portfolio_exposure(self):
        result = calculate_sector_exposure("Unknown Fund")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_unknown_portfolio_health(self):
        result = analyze_portfolio_health("Unknown Fund")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_unknown_portfolio_risk(self):
        result = analyze_portfolio_risk("Unknown Fund")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_invalid_sql_table(self):
        result = run_sql_query("SELECT * FROM fake_table")
        self.assertFalse(result["success"])
        self.assertIn("no such table", result["error"])

    def test_valid_cte_query(self):
        result = run_sql_query(
            "WITH portfolio_count AS "
            "(SELECT COUNT(*) AS total FROM portfolios) "
            "SELECT total FROM portfolio_count"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["rows"][0]["total"], 13)

    def test_sql_rejects_update(self):
        result = run_sql_query(
            "UPDATE portfolios SET status = 'Inactive'"
        )
        self.assertFalse(result["success"])
        self.assertIn("SELECT", result["error"])



    def test_sql_rejects_insert(self):
        result = run_sql_query(
            "INSERT INTO portfolios (portfolio_name) VALUES ('Test Fund')"
        )
        self.assertFalse(result["success"])

    def test_sql_rejects_drop_table(self):
        result = run_sql_query("DROP TABLE portfolios")
        self.assertFalse(result["success"])

    def test_sql_rejects_alter_table(self):
        result = run_sql_query(
            "ALTER TABLE portfolios ADD COLUMN test_column TEXT"
        )
        self.assertFalse(result["success"])

    def test_sql_rejects_multiple_statements(self):
        result = run_sql_query(
            "SELECT COUNT(*) FROM portfolios; DELETE FROM portfolios"
        )
        self.assertFalse(result["success"])

    def test_sql_rejects_pragma_write(self):
        result = run_sql_query("PRAGMA user_version = 999")
        self.assertFalse(result["success"])

    def test_sql_rejects_create_table(self):
        result = run_sql_query(
            "CREATE TABLE test_table (id INTEGER)"
        )
        self.assertFalse(result["success"])

if __name__ == "__main__":
    unittest.main()
