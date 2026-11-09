"""
Tests for the Portfolio Reconciliation Engine.
All tests run offline against the actual supplied database — no Gemini API needed.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from reconciliation import reconcile_portfolio


class TestReconciliation(unittest.TestCase):

    # ------------------------------------------------------------------ #
    # Structural / smoke tests against real DB portfolios                  #
    # ------------------------------------------------------------------ #

    def test_tech_innovation_fund_reconciles_successfully(self):
        """Tech Innovation Fund is a pure-equity portfolio — should reconcile cleanly."""
        result = reconcile_portfolio("Tech Innovation Fund")
        self.assertTrue(result["success"], msg=result.get("error"))
        self.assertEqual(result["portfolio_name"], "Tech Innovation Fund")
        self.assertIn("reconciliation_status", result)
        self.assertIn(result["reconciliation_status"], ("clean", "warnings", "errors"))

    def test_growth_equity_fund_reconciles_successfully(self):
        """Growth Equity Fund — second real-DB portfolio smoke test."""
        result = reconcile_portfolio("Growth Equity Fund")
        self.assertTrue(result["success"], msg=result.get("error"))
        self.assertEqual(result["portfolio_name"], "Growth Equity Fund")
        self.assertGreater(result["total_market_value"], 0)

    def test_balanced_portfolio_reconciles_successfully(self):
        """Balanced Portfolio — mixed stock/bond portfolio."""
        result = reconcile_portfolio("Balanced Portfolio")
        self.assertTrue(result["success"], msg=result.get("error"))
        self.assertEqual(result["portfolio_name"], "Balanced Portfolio")

    def test_result_has_all_required_keys(self):
        """Result structure must contain all documented keys (v2)."""
        result = reconcile_portfolio("Tech Innovation Fund")
        self.assertTrue(result["success"])
        required_keys = [
            "portfolio_name", "status", "reconciliation_status",
            "total_market_value", "recorded_total_weight", "weight_drift",
            "allocation_drift", "aum_coverage", "total_cost_basis",
            "holdings_count", "holdings", "discrepancies",
            "duplicate_securities", "zero_weight_holdings",
            "validation_errors", "data_completeness_pct",
            "summary", "thresholds", "methodology", "data_note",
        ]
        for key in required_keys:
            self.assertIn(key, result, msg=f"Missing key: {key}")

    def test_holdings_detail_structure(self):
        """Each holding entry must have the documented fields (v2)."""
        result = reconcile_portfolio("Tech Innovation Fund")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["holdings"]), 0)
        required_fields = [
            "symbol", "company_name", "asset_type", "quantity",
            "current_price", "market_value", "recorded_weight",
            "computed_weight", "weight_drift", "status", "validation",
        ]
        for holding in result["holdings"]:
            for field in required_fields:
                self.assertIn(field, holding, msg=f"Holding missing field: {field}")

    def test_summary_counts_are_consistent(self):
        """summary totals must add up to total holdings (using v2 key names)."""
        result = reconcile_portfolio("Growth Equity Fund")
        self.assertTrue(result["success"])
        s = result["summary"]
        total = (
            s["matched_count"] + s["observation_count"] +
            s["discrepancy_count"] + s["incomplete_count"] + s["invalid_count"]
        )
        self.assertEqual(total, s["total_holdings"])

    # ------------------------------------------------------------------ #
    # Error handling                                                        #
    # ------------------------------------------------------------------ #

    def test_unknown_portfolio_returns_error(self):
        """Non-existent portfolio name must return success=False with error message."""
        result = reconcile_portfolio("Nonexistent Fund XYZ")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_empty_portfolio_name_returns_error(self):
        """Empty string must return success=False."""
        result = reconcile_portfolio("")
        self.assertFalse(result["success"])

    # ------------------------------------------------------------------ #
    # Weight arithmetic                                                     #
    # ------------------------------------------------------------------ #

    def test_computed_weights_sum_to_one(self):
        """Sum of computed_weight across priceable holdings must equal 1.0 (±0.001)."""
        result = reconcile_portfolio("Tech Innovation Fund")
        self.assertTrue(result["success"])
        priceable = [h for h in result["holdings"] if h["computed_weight"] is not None]
        if priceable:
            total_computed = sum(h["computed_weight"] for h in priceable)
            self.assertAlmostEqual(total_computed, 1.0, places=3,
                                   msg=f"Computed weights sum to {total_computed}, expected ~1.0")

    def test_thresholds_are_documented(self):
        """Thresholds dict must document warning and error percentage levels."""
        result = reconcile_portfolio("Tech Innovation Fund")
        self.assertTrue(result["success"])
        thresholds = result["thresholds"]
        self.assertIn("warning_threshold_pct", thresholds)
        self.assertIn("error_threshold_pct", thresholds)
        # Error threshold must be strictly larger than warning threshold
        self.assertGreater(
            thresholds["error_threshold_pct"],
            thresholds["warning_threshold_pct"]
        )


if __name__ == "__main__":
    unittest.main()
