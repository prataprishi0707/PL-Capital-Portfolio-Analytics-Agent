"""
Tests for enhanced analytics: health_score, risk_score/tier, comparison winner logic.
All run offline against the actual supplied database.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from portfolio_health import analyze_portfolio_health
from risk_analyzer import analyze_portfolio_risk
from portfolio_comparison import compare_portfolios


class TestHealthScore(unittest.TestCase):

    def test_health_score_is_present(self):
        """health_score must be present in analyze_portfolio_health result."""
        result = analyze_portfolio_health("Tech Innovation Fund")
        self.assertTrue(result["success"])
        self.assertIn("health_score", result)

    def test_health_score_is_in_valid_range(self):
        """health_score must be between 0 and 100 inclusive."""
        for name in ["Tech Innovation Fund", "Balanced Portfolio", "Growth Equity Fund"]:
            with self.subTest(portfolio=name):
                result = analyze_portfolio_health(name)
                self.assertTrue(result["success"])
                score = result["health_score"]
                self.assertIsInstance(score, int)
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 100)

    def test_health_tier_matches_score(self):
        """health_tier must be consistent with health_score thresholds."""
        result = analyze_portfolio_health("Growth Equity Fund")
        self.assertTrue(result["success"])
        score = result["health_score"]
        tier = result["health_tier"]
        if score >= 80:
            self.assertEqual(tier, "healthy")
        elif score >= 55:
            self.assertEqual(tier, "moderate")
        else:
            self.assertEqual(tier, "attention_needed")

    def test_health_score_note_is_documented(self):
        """health_score_note field must be present and non-empty."""
        result = analyze_portfolio_health("Conservative Income Fund")
        self.assertTrue(result["success"])
        self.assertIn("health_score_note", result)
        self.assertTrue(len(result["health_score_note"]) > 10)

    def test_full_data_portfolio_scores_at_least_60(self):
        """A portfolio with full data and no high alerts should score reasonably high."""
        result = analyze_portfolio_health("Conservative Income Fund")
        self.assertTrue(result["success"])
        # Conservative Income Fund is low-risk; should not score below 60
        # unless the data contains alerts (we don't fabricate the threshold — we verify)
        if result["analysis_status"] == "full":
            high_alerts = [a for a in result["alerts"] if a["severity"] == "high"]
            if not high_alerts:
                self.assertGreaterEqual(result["health_score"], 60,
                    msg="Full-data, no-high-alert portfolio scored below 60 — check formula")


class TestRiskScore(unittest.TestCase):

    def test_risk_score_is_present(self):
        """risk_score must be present in analyze_portfolio_risk result."""
        result = analyze_portfolio_risk("Tech Innovation Fund")
        self.assertTrue(result["success"])
        self.assertIn("risk_score", result)
        self.assertIn("risk_tier", result)

    def test_risk_score_is_in_valid_range(self):
        """risk_score must be 0–100 for all real portfolios."""
        for name in ["Tech Innovation Fund", "Balanced Portfolio", "Growth Equity Fund"]:
            with self.subTest(portfolio=name):
                result = analyze_portfolio_risk(name)
                self.assertTrue(result["success"])
                score = result["risk_score"]
                self.assertIsInstance(score, int)
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 100)

    def test_risk_tier_matches_score(self):
        """risk_tier must be consistent with the documented rule:
        tier is the score-derived tier CAPPED by the authoritative signal level.
        A high signal can NEVER produce a non-aggressive tier."""
        result = analyze_portfolio_risk("Balanced Portfolio")
        self.assertTrue(result["success"])
        score = result["risk_score"]
        tier = result["risk_tier"]
        signal = result["risk_level"]
        score_tier = result["score_tier_uncapped"]

        # The capped rule:
        if signal == "high":
            self.assertEqual(tier, "aggressive",
                msg=f"high signal must force aggressive tier; got {tier} (score={score})")
        elif signal == "moderate":
            self.assertIn(tier, ("moderate", "aggressive"))
        elif signal == "not_assessed":
            self.assertEqual(tier, "not_assessed")
        else:  # lower_observed_signals
            # uncapped score tier applies
            if score >= 70:
                self.assertEqual(tier, "conservative")
            elif score >= 40:
                self.assertEqual(tier, "moderate")
            else:
                self.assertEqual(tier, "aggressive")

    def test_high_signal_never_hidden_by_high_score(self):
        """Adversarial: a portfolio with a high risk signal must report
        risk_level=high AND risk_tier=aggressive, even if the score is high."""
        for name in ["Balanced Portfolio", "Conservative Income Fund",
                     "Tech Innovation Fund", "Growth Equity Fund"]:
            with self.subTest(portfolio=name):
                r = analyze_portfolio_risk(name)
                self.assertTrue(r["success"])
                if r["risk_level"] == "high":
                    self.assertEqual(r["risk_tier"], "aggressive",
                        msg=f"{name}: high signal but tier={r['risk_tier']} (score={r['risk_score']})")
                    # The headline must not be hidden.
                    self.assertEqual(r["risk_level"], "high")
                    # Uncapped score tier is reported separately for transparency.
                    self.assertIn("score_tier_uncapped", r)

    def test_data_completeness_present(self):
        """data_completeness_pct and assessment_confidence must be reported."""
        r = analyze_portfolio_risk("Tech Innovation Fund")
        self.assertTrue(r["success"])
        self.assertIn("data_completeness_pct", r)
        self.assertIn("assessment_confidence", r)
        self.assertIn("consistency_note", r)
        self.assertGreater(r["data_completeness_pct"], 0)
        self.assertIn(r["assessment_confidence"], ("high", "medium", "low"))

    def test_risk_score_note_documented(self):
        """risk_score_note must be present and non-empty."""
        result = analyze_portfolio_risk("Tech Innovation Fund")
        self.assertTrue(result["success"])
        self.assertIn("risk_score_note", result)
        self.assertTrue(len(result["risk_score_note"]) > 10)


class TestComparisonWinner(unittest.TestCase):

    def test_comparison_has_winner_fields(self):
        """compare_portfolios result must contain winner metadata."""
        result = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(result["success"])
        self.assertIn("overall_winner", result)
        self.assertIn("wins_portfolio_1", result)
        self.assertIn("wins_portfolio_2", result)
        self.assertIn("comparison_summary", result)
        self.assertIn("winner_note", result)

    def test_per_metric_winner_field_present(self):
        """Each metric in performance_and_risk must have a 'winner' key."""
        result = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(result["success"])
        for metric, item in result["performance_and_risk"].items():
            self.assertIn("winner", item,
                          msg=f"Metric '{metric}' is missing 'winner' field")

    def test_winner_values_are_valid(self):
        """winner field values must be one of the documented valid strings."""
        valid_winners = {"portfolio_1", "portfolio_2", "tie", "unavailable"}
        result = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(result["success"])
        for metric, item in result["performance_and_risk"].items():
            self.assertIn(item["winner"], valid_winners,
                          msg=f"Metric '{metric}' has invalid winner: {item['winner']}")

    def test_win_counts_are_consistent(self):
        """wins_portfolio_1 + wins_portfolio_2 must equal counted wins in metrics."""
        result = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(result["success"])
        metrics = result["performance_and_risk"]
        manual_w1 = sum(1 for m in metrics.values() if m["winner"] == "portfolio_1")
        manual_w2 = sum(1 for m in metrics.values() if m["winner"] == "portfolio_2")
        self.assertEqual(result["wins_portfolio_1"], manual_w1)
        self.assertEqual(result["wins_portfolio_2"], manual_w2)

    def test_comparison_summary_is_non_empty_string(self):
        """comparison_summary must be a non-empty string."""
        result = compare_portfolios("Conservative Income Fund", "Balanced Portfolio")
        self.assertTrue(result["success"])
        self.assertIsInstance(result["comparison_summary"], str)
        self.assertGreater(len(result["comparison_summary"]), 5)


if __name__ == "__main__":
    unittest.main()
