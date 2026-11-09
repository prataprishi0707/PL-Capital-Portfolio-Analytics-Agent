"""
Adversarial tests (v3 — controlled data, partial-denominator rejection,
coverage-threshold winner logic).

These tests use isolated calculation helpers (_reconcile_holdings and
_decide_overall_winner) so scenarios are guaranteed to execute regardless of
what the production database happens to contain. The original protected
database is never modified.

A regression to the old behaviour makes these tests FAIL.
"""

import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from reconciliation import (
    validate_numeric, reconcile_holding, reconcile_portfolio,
    _reconcile_holdings,
    STATUS_MATCHED, STATUS_OBSERVATION, STATUS_DISCREPANCY,
    STATUS_INCOMPLETE, STATUS_INVALID,
)
from risk_analyzer import analyze_portfolio_risk, _is_valid_number
from portfolio_comparison import (
    compare_portfolios, _decide_overall_winner, _is_finite_number,
    MIN_COMPARABLE_METRICS, MIN_COVERAGE_PCT, MIN_WIN_MARGIN,
)


# --------------------------------------------------------------------------- #
# Helpers to build controlled holding dicts                                    #
# --------------------------------------------------------------------------- #
def _h(symbol, quantity, price, weight, cost_basis=None,
       company="Co", asset_type="Stock"):
    return {
        "symbol": symbol, "company_name": company, "asset_type": asset_type,
        "quantity": quantity, "current_price": price,
        "current_weight": weight, "cost_basis": cost_basis,
    }


NAN = float("nan")
INF = float("inf")


# --------------------------------------------------------------------------- #
# validate_numeric                                                             #
# --------------------------------------------------------------------------- #
class TestValidateNumeric(unittest.TestCase):

    def test_none_is_missing_not_zero(self):
        status, val, err = validate_numeric(None, "x", allow_none=False)
        self.assertEqual(status, "missing")
        self.assertIsNone(val)

    def test_none_allowed(self):
        status, val, err = validate_numeric(None, "x", allow_none=True)
        self.assertEqual(status, "valid")
        self.assertIsNone(val)

    def test_nan_is_invalid(self):
        self.assertEqual(validate_numeric(float("nan"), "x")[0], "invalid")

    def test_positive_infinity_is_invalid(self):
        self.assertEqual(validate_numeric(float("inf"), "x")[0], "invalid")

    def test_negative_infinity_is_invalid(self):
        self.assertEqual(validate_numeric(float("-inf"), "x")[0], "invalid")

    def test_invalid_string_is_invalid(self):
        for v in ["abc", "N/A", "--", "twelve", "$100"]:
            self.assertEqual(validate_numeric(v, "x")[0], "invalid",
                             msg=f"{v!r} should be invalid")

    def test_valid_numeric_string_is_accepted(self):
        status, val, err = validate_numeric("3.14", "x")
        self.assertEqual(status, "valid")
        self.assertAlmostEqual(val, 3.14)

    def test_negative_value_rejected_by_default(self):
        self.assertEqual(validate_numeric(-5.0, "price")[0], "invalid")

    def test_negative_allowed_when_flagged(self):
        self.assertEqual(validate_numeric(-5.0, "x", allow_negative=True)[0], "valid")

    def test_zero_rejected_when_disallowed(self):
        self.assertEqual(validate_numeric(0, "price", allow_zero=False)[0], "invalid")

    def test_zero_allowed_by_default(self):
        self.assertEqual(validate_numeric(0, "weight")[0], "valid")

    def test_boolean_rejected(self):
        self.assertEqual(validate_numeric(True, "x")[0], "invalid")
        self.assertEqual(validate_numeric(False, "x")[0], "invalid")

    def test_empty_string_is_missing(self):
        self.assertEqual(validate_numeric("", "x", allow_none=False)[0], "missing")

    def test_huge_finite_value_accepted(self):
        self.assertEqual(validate_numeric(1e300, "x")[0], "valid")


# --------------------------------------------------------------------------- #
# _is_valid_number                                                              #
# --------------------------------------------------------------------------- #
class TestIsValidNumber(unittest.TestCase):

    def test_none_invalid(self):
        self.assertFalse(_is_valid_number(None))

    def test_nan_invalid(self):
        self.assertFalse(_is_valid_number(float("nan")))

    def test_inf_invalid(self):
        self.assertFalse(_is_valid_number(float("inf")))
        self.assertFalse(_is_valid_number(float("-inf")))

    def test_bool_invalid(self):
        self.assertFalse(_is_valid_number(True))

    def test_string_invalid(self):
        self.assertFalse(_is_valid_number("1.5"))

    def test_finite_number_valid(self):
        self.assertTrue(_is_valid_number(3.14))
        self.assertTrue(_is_valid_number(0))
        self.assertTrue(_is_valid_number(-2.5))


# --------------------------------------------------------------------------- #
# reconcile_holding — per-holding validation                                    #
# --------------------------------------------------------------------------- #
class TestReconcileHolding(unittest.TestCase):

    def _base(self, **ov):
        d = _h("TST", 100, 50.0, 0.5, cost_basis=5000.0)
        d.update(ov)
        return d

    def test_valid_holding_no_validation_errors(self):
        h = reconcile_holding(self._base())
        self.assertEqual(h["validation"], {})
        self.assertIsNotNone(h["market_value"])

    def test_null_quantity_is_incomplete_not_zero(self):
        h = reconcile_holding(self._base(quantity=None))
        self.assertIn("quantity", h["validation"])
        self.assertIn(h["status"], (STATUS_INCOMPLETE, STATUS_INVALID))

    def test_null_price_is_incomplete(self):
        h = reconcile_holding(self._base(current_price=None))
        self.assertEqual(h["status"], STATUS_INCOMPLETE)

    def test_nan_price_is_invalid(self):
        h = reconcile_holding(self._base(current_price=float("nan")))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_inf_quantity_is_invalid(self):
        h = reconcile_holding(self._base(quantity=float("inf")))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_negative_price_is_invalid(self):
        h = reconcile_holding(self._base(current_price=-10.0))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_negative_quantity_is_invalid(self):
        h = reconcile_holding(self._base(quantity=-5))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_invalid_string_weight_is_invalid(self):
        h = reconcile_holding(self._base(current_weight="abc"))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_nan_weight_is_invalid(self):
        h = reconcile_holding(self._base(current_weight=float("nan")))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_overflow_market_value_is_handled(self):
        h = reconcile_holding(self._base(quantity=1e308, current_price=1e308))
        self.assertIn(h["status"], (STATUS_INVALID, STATUS_INCOMPLETE))
        self.assertIsNone(h["market_value"])

    def test_zero_price_is_invalid(self):
        h = reconcile_holding(self._base(current_price=0.0))
        self.assertEqual(h["status"], STATUS_INVALID)

    def test_matched_holding_not_returned_when_invalid(self):
        h = reconcile_holding(self._base(current_price=float("nan")))
        self.assertNotEqual(h["status"], STATUS_MATCHED)


# --------------------------------------------------------------------------- #
# FIX 1 — partial-denominator rejection (controlled data via pure helper)      #
# --------------------------------------------------------------------------- #
class TestPartialDenominator(unittest.TestCase):
    """A normalised weight is only meaningful over a COMPLETE denominator.
    If any holding is incomplete/invalid, NO holding receives MATCHED,
    computed_weight, or a normalised weight. Allocation drift is INCOMPLETE
    when any recorded weight is missing/invalid. AUM coverage is not assessed
    on a partial market value."""

    def _run(self, holdings, aum=None):
        return _reconcile_holdings(holdings, aum, "TestPortfolio")

    # --- Required cases -------------------------------------------------- #

    def test_case_one_missing_current_price(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, None, 0.5, cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertFalse(h["market_denominator_complete"])
        self.assertEqual(h["status"], STATUS_INCOMPLETE)
        for holding in h["holdings"]:
            self.assertNotEqual(holding["status"], STATUS_MATCHED)
            self.assertIsNone(holding["computed_weight"])
        self.assertEqual(h["aum_coverage"]["status"], STATUS_INCOMPLETE)

    def test_case_one_missing_quantity(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", None, 50.0, 0.5, cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertFalse(h["market_denominator_complete"])
        self.assertEqual(h["status"], STATUS_INCOMPLETE)
        for holding in h["holdings"]:
            self.assertNotEqual(holding["status"], STATUS_MATCHED)
            self.assertIsNone(holding["computed_weight"])

    def test_case_one_invalid_price(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, float("nan"), 0.5, cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertEqual(h["status"], STATUS_INVALID)
        # INVALID must be distinct from INCOMPLETE.
        self.assertTrue(any(s["status"] == STATUS_INVALID for s in h["holdings"]))
        for holding in h["holdings"]:
            self.assertNotEqual(holding["status"], STATUS_MATCHED)

    def test_case_one_missing_current_weight(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, 50.0, None, cost_basis=5000.0),
        ], aum=1_000_000)
        # B is missing its recorded weight => B is INCOMPLETE. The market-value
        # reconciliation is therefore incomplete: we cannot compute drift for B
        # (no recorded weight to compare against), so NO holding is normalised.
        self.assertFalse(h["market_denominator_complete"])
        self.assertFalse(h["allocation_assessable"])
        self.assertEqual(h["allocation_drift"]["status"], STATUS_INCOMPLETE)
        # No holding is MATCHED; A becomes INCOMPLETE due to the partial basis.
        self.assertEqual(h["status"], STATUS_INCOMPLETE)
        for holding in h["holdings"]:
            self.assertNotEqual(holding["status"], STATUS_MATCHED)

    def test_case_one_invalid_current_weight(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, 50.0, float("nan"), cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertEqual(h["status"], STATUS_INVALID)
        self.assertEqual(h["allocation_drift"]["status"], STATUS_INCOMPLETE)

    def test_case_one_missing_cost_basis(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, 50.0, 0.5, cost_basis=None),
        ], aum=1_000_000)
        # Market denominator complete; cost-basis denominator incomplete.
        self.assertTrue(h["market_denominator_complete"])
        self.assertFalse(h["cost_basis_denominator_complete"])
        # No holding should have a normalised cost-basis weight from a partial set.
        for holding in h["holdings"]:
            self.assertIsNone(holding["cost_basis_weight"])

    def test_case_all_prices_missing(self):
        h = self._run([
            _h("A", 100, None, 0.5, cost_basis=5000.0),
            _h("B", 100, None, 0.5, cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertFalse(h["market_denominator_complete"])
        self.assertEqual(h["status"], STATUS_INCOMPLETE)
        for holding in h["holdings"]:
            self.assertNotEqual(holding["status"], STATUS_MATCHED)
            self.assertIsNone(holding["computed_weight"])
        self.assertEqual(h["aum_coverage"]["status"], STATUS_INCOMPLETE)

    def test_case_all_weights_missing(self):
        h = self._run([
            _h("A", 100, 50.0, None, cost_basis=5000.0),
            _h("B", 100, 50.0, None, cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertFalse(h["allocation_assessable"])
        self.assertEqual(h["allocation_drift"]["status"], STATUS_INCOMPLETE)
        # Allocation drift must NOT be MATCHED when weights are incomplete.
        self.assertNotEqual(h["allocation_drift"]["status"], STATUS_MATCHED)

    def test_case_one_valid_plus_one_incomplete(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),   # valid on its own
            _h("B", 100, None, 0.5, cost_basis=5000.0),   # incomplete (no price)
        ], aum=1_000_000)
        self.assertFalse(h["market_denominator_complete"])
        self.assertEqual(h["status"], STATUS_INCOMPLETE)
        # A must NOT be MATCHED based on a partial denominator.
        a_holding = next(x for x in h["holdings"] if x["symbol"] == "A")
        self.assertNotEqual(a_holding["status"], STATUS_MATCHED)
        self.assertIsNone(a_holding["computed_weight"])
        # AUM coverage must not be assessed on the partial market value.
        self.assertEqual(h["aum_coverage"]["status"], STATUS_INCOMPLETE)

    def test_case_complete_portfolio_all_valid(self):
        h = self._run([
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, 50.0, 0.5, cost_basis=5000.0),
        ], aum=1_000_000)
        self.assertTrue(h["market_denominator_complete"])
        self.assertTrue(h["allocation_assessable"])
        # With matching weights and prices, all holdings are MATCHED.
        self.assertEqual(h["status"], STATUS_MATCHED)
        for holding in h["holdings"]:
            self.assertEqual(holding["status"], STATUS_MATCHED)
            self.assertIsNotNone(holding["computed_weight"])
        self.assertAlmostEqual(h["holdings"][0]["computed_weight"], 0.5, places=4)

    # --- Cross-case invariants ------------------------------------------- #

    def test_no_matched_on_any_incomplete_denominator(self):
        """Across every incomplete case, no holding is MATCHED and AUM coverage
        is not assessed from partial values."""
        incomplete_cases = [
            [self.test_case_one_missing_current_price.__name__,
             [_h("A", 100, 50.0, 0.5, 5000.0), _h("B", 100, None, 0.5, 5000.0)]],
            [self.test_case_one_missing_quantity.__name__,
             [_h("A", 100, 50.0, 0.5, 5000.0), _h("B", None, 50.0, 0.5, 5000.0)]],
            [self.test_case_all_prices_missing.__name__,
             [_h("A", 100, None, 0.5, 5000.0), _h("B", 100, None, 0.5, 5000.0)]],
        ]
        for name, holdings in incomplete_cases:
            with self.subTest(case=name):
                r = self._run(holdings, aum=1_000_000)
                for holding in r["holdings"]:
                    self.assertNotEqual(holding["status"], STATUS_MATCHED,
                        msg=f"{name}: holding {holding['symbol']} must not be MATCHED")
                self.assertIn(r["aum_coverage"]["status"],
                    (STATUS_INCOMPLETE, "not_assessed"),
                    msg=f"{name}: AUM coverage must not be assessed from partial values")

    def test_invalid_distinct_from_incomplete(self):
        """INVALID_DATA and INCOMPLETE must remain distinct statuses."""
        invalid = self._run([_h("A", 100, 50.0, 0.5, 5000.0),
                             _h("B", 100, float("nan"), 0.5, 5000.0)])
        incomplete = self._run([_h("A", 100, 50.0, 0.5, 5000.0),
                                _h("B", 100, None, 0.5, 5000.0)])
        self.assertEqual(invalid["status"], STATUS_INVALID)
        self.assertEqual(incomplete["status"], STATUS_INCOMPLETE)
        self.assertNotEqual(STATUS_INVALID, STATUS_INCOMPLETE)

    def test_aggregate_reflects_worst_condition(self):
        """When one holding is INVALID, the aggregate is INVALID even if
        another holding would otherwise be MATCHED."""
        h = self._run([
            _h("A", 100, 50.0, 0.5, 5000.0),
            _h("B", 100, float("nan"), 0.5, 5000.0),
        ], aum=1_000_000)
        self.assertEqual(h["status"], STATUS_INVALID)


# --------------------------------------------------------------------------- #
# Real-data reconciliation (still uses the DB; no modification)                 #
# --------------------------------------------------------------------------- #
class TestReconciliationRealData(unittest.TestCase):

    def test_all_13_portfolios_reconcile(self):
        import sqlite3
        DB = PROJECT_ROOT / "portfolio_database.db"
        conn = sqlite3.connect(DB)
        names = [r[0] for r in conn.execute(
            "SELECT portfolio_name FROM portfolios ORDER BY portfolio_id").fetchall()]
        conn.close()
        self.assertEqual(len(names), 13)
        for name in names:
            with self.subTest(portfolio=name):
                r = reconcile_portfolio(name)
                self.assertTrue(r["success"], msg=r.get("error"))
                self.assertIn(r["status"],
                    (STATUS_MATCHED, STATUS_OBSERVATION, STATUS_DISCREPANCY,
                     STATUS_INCOMPLETE, STATUS_INVALID))
                self.assertIn("allocation_drift", r)
                self.assertIn("aum_coverage", r)

    def test_allocation_drift_vs_aum_coverage_distinguished(self):
        r = reconcile_portfolio("Tech Innovation Fund")
        self.assertTrue(r["success"])
        self.assertIn(r["allocation_drift"]["status"],
            (STATUS_MATCHED, STATUS_OBSERVATION, STATUS_DISCREPANCY, STATUS_INCOMPLETE))
        self.assertIn(r["aum_coverage"]["status"],
            (STATUS_MATCHED, STATUS_OBSERVATION, STATUS_INCOMPLETE, "not_assessed"))

    def test_cost_basis_diagnostic_present(self):
        r = reconcile_portfolio("Growth Equity Fund")
        self.assertTrue(r["success"])
        self.assertIn("total_cost_basis", r)
        if r["total_cost_basis"] is not None:
            self.assertTrue(any(h.get("cost_basis_weight") is not None
                                for h in r["holdings"]))


# --------------------------------------------------------------------------- #
# Contradictory risk signals                                                   #
# --------------------------------------------------------------------------- #
class TestContradictoryRiskSignals(unittest.TestCase):

    def test_high_signal_caps_tier_to_aggressive(self):
        r = analyze_portfolio_risk("Balanced Portfolio")
        self.assertTrue(r["success"])
        if r["risk_level"] == "high":
            self.assertEqual(r["risk_tier"], "aggressive")

    def test_score_tier_uncapped_reported_separately(self):
        r = analyze_portfolio_risk("Balanced Portfolio")
        self.assertTrue(r["success"])
        self.assertIn("score_tier_uncapped", r)
        if r["risk_level"] == "high":
            self.assertEqual(r["risk_tier"], "aggressive")

    def test_data_completeness_does_not_imply_safety(self):
        r = analyze_portfolio_risk("Tech Innovation Fund")
        self.assertTrue(r["success"])
        self.assertIn(r["assessment_confidence"], ("high", "medium", "low"))
        if r["data_completeness_pct"] >= 90:
            self.assertEqual(r["assessment_confidence"], "high")
        elif r["data_completeness_pct"] >= 50:
            self.assertEqual(r["assessment_confidence"], "medium")
        else:
            self.assertEqual(r["assessment_confidence"], "low")

    def test_no_fabricated_risk_data(self):
        r = analyze_portfolio_risk("Tech Innovation Fund")
        self.assertTrue(r["success"])
        for metric, details in r["risk_indicators"].items():
            if details["value"] is not None:
                self.assertTrue(_is_valid_number(details["value"]),
                    msg=f"{metric} is not a valid finite number: {details['value']}")

    def test_consistency_note_present_and_explains(self):
        r = analyze_portfolio_risk("Balanced Portfolio")
        self.assertTrue(r["success"])
        note = r["consistency_note"]
        self.assertIn("signal_level", note)
        self.assertIn("risk_score", note)
        self.assertIn("CAPPED", note)


# --------------------------------------------------------------------------- #
# FIX 2 / FIX 3 — comparison coverage and winner logic (pure helper)           #
# --------------------------------------------------------------------------- #
class TestComparisonWinnerLogic(unittest.TestCase):
    """Use the pure _decide_overall_winner helper with controlled metric values
    so coverage-threshold behaviour is deterministic."""

    def _all_metrics(self, v1, v2):
        # All 9 metrics present with the given pair.
        return {
            "total_return_1y": (v1, v2), "volatility": (v1, v2),
            "sharpe_ratio": (v1, v2), "max_drawdown": (v1, v2),
            "beta": (v1, v2), "var_95": (v1, v2), "cvar_95": (v1, v2),
            "sortino_ratio": (v1, v2), "tracking_error": (v1, v2),
        }

    def test_decisive_margin_declares_winner(self):
        # 5 higher-is-better metrics favour p1, 4 risk metrics favour p1
        # (lower abs) -> margin large, coverage 100%.
        mv = {
            "total_return_1y": (10, 5), "sharpe_ratio": (2, 1),
            "sortino_ratio": (2, 1), "volatility": (10, 20),
            "max_drawdown": (-5, -15), "beta": (0.8, 1.2),
            "var_95": (-2, -4), "cvar_95": (-3, -5), "tracking_error": (1, 3),
        }
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["overall_winner"], "P1")
        self.assertEqual(d["overall_winner_key"], "portfolio_1")
        self.assertGreaterEqual(d["wins_1"] - d["wins_2"], MIN_WIN_MARGIN)

    def test_coverage_below_threshold_no_winner(self):
        # Only 2 comparable metrics -> below MIN_COMPARABLE_METRICS (4).
        mv = self._all_metrics(10, 10)
        mv["total_return_1y"] = (10, 5)   # p1 wins
        mv["sharpe_ratio"] = (2, 1)       # p1 wins
        # All others equal -> ties. comparable = 9, but wins_1=2, wins_2=0, ties=7.
        # coverage = 9/9 = 100% (>= 60%), comparable 9 (>= 4). margin = 2 (>= 2).
        # Actually this WOULD declare a winner. Let me instead make coverage low.
        d = _decide_overall_winner(mv, "P1", "P2")
        # 9 comparable, margin 2 -> winner. Adjust to truly insufficient coverage:
        mv2 = {}
        for k in ("total_return_1y", "volatility", "sharpe_ratio"):
            mv2[k] = (10, 5)
        # 3 metrics total, all p1 wins -> comparable 3 (< 4) -> insufficient.
        d2 = _decide_overall_winner(mv2, "P1", "P2")
        self.assertEqual(d2["overall_winner"], "no_defensible_winner",
            msg="coverage below threshold must yield no_defensible_winner")
        self.assertEqual(d2["overall_winner_key"], "no_defensible_winner")

    def test_coverage_exactly_at_threshold(self):
        # 6 of 9 comparable = 66.7% (>= 60%), 6 >= 4. margin decisive.
        mv = self._all_metrics(None, None)  # 3 unavailable
        mv["total_return_1y"] = (10, 5)
        mv["sharpe_ratio"] = (2, 1)
        mv["sortino_ratio"] = (2, 1)
        mv["volatility"] = (10, 20)
        mv["max_drawdown"] = (-5, -15)
        mv["beta"] = (0.8, 1.2)
        # 6 comparable, p1 wins all 6 -> margin 6 >= 2 -> winner.
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["comparable_metrics_count"], 6)
        self.assertGreaterEqual(d["metric_coverage_pct"], MIN_COVERAGE_PCT)
        self.assertEqual(d["overall_winner"], "P1")

    def test_coverage_just_below_threshold(self):
        # 5 of 9 comparable = 55.6% (< 60%) -> insufficient even though 5 >= 4.
        mv = self._all_metrics(None, None)  # 4 unavailable
        mv["total_return_1y"] = (10, 5)
        mv["sharpe_ratio"] = (2, 1)
        mv["sortino_ratio"] = (2, 1)
        mv["volatility"] = (10, 20)
        mv["max_drawdown"] = (-5, -15)
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["comparable_metrics_count"], 5)
        self.assertLess(d["metric_coverage_pct"], MIN_COVERAGE_PCT)
        self.assertEqual(d["overall_winner"], "no_defensible_winner")

    def test_equal_wins_yields_tie_not_no_winner(self):
        # Sufficient coverage, equal wins -> genuine tie (NOT no_defensible_winner).
        mv = self._all_metrics(10, 10)  # all ties -> equal wins 0 each, ties 9
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["wins_1"], 0)
        self.assertEqual(d["wins_2"], 0)
        self.assertEqual(d["ties"], 9)
        self.assertEqual(d["overall_winner"], "tie")
        self.assertEqual(d["overall_winner_key"], "tie")
        # Ties must not be counted as wins.
        self.assertEqual(d["wins_1"] + d["wins_2"], 0)

    def test_indecisive_small_margin_no_winner(self):
        # Sufficient coverage, margin of exactly 1 (< MIN_WIN_MARGIN) -> no winner.
        mv = self._all_metrics(10, 10)
        mv["total_return_1y"] = (10, 5)  # p1 wins one, rest ties
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["wins_1"], 1)
        self.assertEqual(d["wins_2"], 0)
        self.assertEqual(d["overall_winner"], "no_defensible_winner",
            msg="margin < threshold must yield no_defensible_winner, not a winner")

    def test_unavailable_not_counted_as_tie_or_win(self):
        mv = self._all_metrics(None, None)  # all unavailable
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["unavailable_count"], 9)
        self.assertEqual(d["comparable_metrics_count"], 0)
        self.assertEqual(d["wins_1"], 0)
        self.assertEqual(d["wins_2"], 0)
        self.assertEqual(d["ties"], 0)
        self.assertEqual(d["overall_winner"], "no_defensible_winner")

    def test_nan_inputs_are_unavailable_not_ties(self):
        # A NaN or infinity must never become an accidental tie.
        mv = self._all_metrics(float("nan"), 10)
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["unavailable_count"], 9)
        self.assertEqual(d["ties"], 0)
        self.assertEqual(d["overall_winner"], "no_defensible_winner")

    def test_infinity_inputs_are_unavailable_not_ties(self):
        mv = self._all_metrics(float("inf"), 10)
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["unavailable_count"], 9)
        self.assertEqual(d["ties"], 0)

    def test_winner_reason_explains_decision(self):
        mv = self._all_metrics(None, None)
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertIsInstance(d["winner_reason"], str)
        self.assertGreater(len(d["winner_reason"]), 10)
        self.assertIn("coverage", d["winner_reason"].lower())


# --------------------------------------------------------------------------- #
# Comparison via the DB-backed path (integration)                              #
# --------------------------------------------------------------------------- #
class TestComparisonInsufficientData(unittest.TestCase):

    def test_comparison_reports_coverage_fields(self):
        r = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(r["success"])
        for key in ["comparable_metrics_count", "total_metrics",
                    "unavailable_metric_count", "metric_coverage_pct",
                    "overall_winner", "winner_reason", "ties"]:
            self.assertIn(key, r, msg=f"missing coverage field: {key}")

    def test_no_defensible_winner_explicit_when_coverage_low(self):
        """FIX 3: explicitly assert == 'no_defensible_winner' when coverage is
        insufficient. Total Bond Market Index Fund vs Fixed Income Plus have
        largely non-overlapping metrics (bond fund has no equity risk metrics
        like beta/var in the same form), so coverage is low."""
        r = compare_portfolios("Total Bond Market Index Fund", "Fixed Income Plus")
        self.assertTrue(r["success"])
        # The winner is always a documented value.
        self.assertIn(r["overall_winner"], (
            r["portfolio_1"], r["portfolio_2"], "tie", "no_defensible_winner"))
        # If coverage is below threshold, it MUST be no_defensible_winner.
        if r["metric_coverage_pct"] < MIN_COVERAGE_PCT or \
           r["comparable_metrics_count"] < MIN_COMPARABLE_METRICS:
            self.assertEqual(r["overall_winner"], "no_defensible_winner",
                msg=f"insufficient coverage ({r['metric_coverage_pct']}%, "
                    f"{r['comparable_metrics_count']} comparable) must give "
                    f"no_defensible_winner, got {r['overall_winner']}")

    def test_same_portfolio_rejected(self):
        r = compare_portfolios("Tech Innovation Fund", "Tech Innovation Fund")
        self.assertFalse(r["success"])

    def test_coverage_pct_consistent_with_counts(self):
        r = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(r["success"])
        total = r["total_metrics"]
        comp = r["comparable_metrics_count"]
        expected = round(comp / total * 100, 2) if total else 0.0
        self.assertEqual(r["metric_coverage_pct"], expected)

    def test_ties_plus_wins_equal_comparable(self):
        r = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(r["success"])
        self.assertEqual(
            r["ties"] + r["wins_portfolio_1"] + r["wins_portfolio_2"],
            r["comparable_metrics_count"]
        )

    def test_winner_reason_is_non_empty_string(self):
        r = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(r["success"])
        self.assertIsInstance(r["winner_reason"], str)
        self.assertGreater(len(r["winner_reason"]), 5)

    def test_allocation_sector_distinguish_unavailable_from_zero(self):
        """Missing allocation/sector values must be None (unavailable), not 0."""
        r = compare_portfolios("Tech Innovation Fund", "Growth Equity Fund")
        self.assertTrue(r["success"])
        for asset_type, vals in r["asset_allocation_comparison"].items():
            self.assertIn("portfolio_1_available", vals)
            self.assertIn("portfolio_2_available", vals)
        for sector, vals in r["sector_exposure_comparison"].items():
            self.assertIn("portfolio_1_available", vals)
            self.assertIn("portfolio_2_available", vals)


# --------------------------------------------------------------------------- #
# _is_finite_number (comparison module)                                        #
# --------------------------------------------------------------------------- #
class TestComparisonIsFinite(unittest.TestCase):

    def test_none_invalid(self):
        self.assertFalse(_is_finite_number(None))

    def test_nan_invalid(self):
        self.assertFalse(_is_finite_number(float("nan")))

    def test_inf_invalid(self):
        self.assertFalse(_is_finite_number(float("inf")))

    def test_string_invalid(self):
        self.assertFalse(_is_finite_number("1.5"))

    def test_finite_valid(self):
        self.assertTrue(_is_finite_number(3.14))
        self.assertTrue(_is_finite_number(0))

    def test_huge_positive_integer_overflow_is_unavailable(self):
        """10**400 cannot be represented as float; must be unavailable, not crash."""
        self.assertFalse(_is_finite_number(10**400))

    def test_huge_negative_integer_overflow_is_unavailable(self):
        self.assertFalse(_is_finite_number(-(10**400)))


# --------------------------------------------------------------------------- #
# FIX 1 (v4) — Invalid AUM distinguished from missing AUM                      #
# --------------------------------------------------------------------------- #
class TestAumValidation(unittest.TestCase):
    """Distinguish missing AUM (None) from invalid AUM (NaN/inf/string/negative).
    Missing -> not_assessed. Invalid -> INVALID_DATA + validation error, and the
    aggregate portfolio status reflects INVALID_DATA. Coverage is never computed
    from an invalid AUM."""

    def _valid_holdings(self):
        # Two fully-comparable holdings so the holdings reconciliation is clean.
        return [
            _h("A", 100, 50.0, 0.5, cost_basis=5000.0),
            _h("B", 100, 50.0, 0.5, cost_basis=5000.0),
        ]

    def _run(self, aum):
        return _reconcile_holdings(self._valid_holdings(), aum, "TestPortfolio")

    def test_aum_none_is_missing_not_invalid(self):
        r = self._run(None)
        self.assertEqual(r["aum_coverage"]["aum_status"], "missing")
        self.assertEqual(r["aum_coverage"]["status"], "not_assessed")
        # Missing AUM must NOT be INVALID_DATA and must NOT add a validation error.
        self.assertNotEqual(r["aum_coverage"]["status"], STATUS_INVALID)
        self.assertFalse(any("total_aum" in ve.get("errors", {})
                              for ve in r["validation_errors"]))

    def test_aum_nan_is_invalid(self):
        r = self._run(float("nan"))
        self.assertEqual(r["aum_coverage"]["aum_status"], "invalid")
        self.assertEqual(r["aum_coverage"]["status"], STATUS_INVALID)
        # Aggregate must reflect INVALID_DATA.
        self.assertEqual(r["status"], STATUS_INVALID)
        # A validation error must be recorded.
        self.assertTrue(any("total_aum" in ve.get("errors", {})
                            for ve in r["validation_errors"]))
        # Coverage must NOT be computed from an invalid value.
        self.assertIsNone(r["aum_coverage"]["coverage_pct"])

    def test_aum_positive_infinity_is_invalid(self):
        r = self._run(float("inf"))
        self.assertEqual(r["aum_coverage"]["aum_status"], "invalid")
        self.assertEqual(r["aum_coverage"]["status"], STATUS_INVALID)
        self.assertEqual(r["status"], STATUS_INVALID)
        self.assertIsNone(r["aum_coverage"]["coverage_pct"])

    def test_aum_negative_is_invalid(self):
        r = self._run(-5_000_000)
        self.assertEqual(r["aum_coverage"]["aum_status"], "invalid")
        self.assertEqual(r["aum_coverage"]["status"], STATUS_INVALID)
        self.assertEqual(r["status"], STATUS_INVALID)
        self.assertIsNone(r["aum_coverage"]["coverage_pct"])

    def test_aum_invalid_string_is_invalid(self):
        r = self._run("not_a_number")
        self.assertEqual(r["aum_coverage"]["aum_status"], "invalid")
        self.assertEqual(r["aum_coverage"]["status"], STATUS_INVALID)
        self.assertEqual(r["status"], STATUS_INVALID)

    def test_aum_valid_positive_assesses_coverage(self):
        # Market value = 2 * (100*50) = 10000. AUM = 1_000_000 -> coverage 1%.
        # 1% < 5 -> OBSERVATION (extreme margin), but the AUM itself is valid.
        r = self._run(1_000_000)
        self.assertEqual(r["aum_coverage"]["aum_status"], "valid")
        self.assertNotEqual(r["aum_coverage"]["status"], STATUS_INVALID)
        self.assertIsNotNone(r["aum_coverage"]["coverage_pct"])
        # No portfolio-level AUM validation error.
        self.assertFalse(any("total_aum" in ve.get("errors", {})
                              for ve in r["validation_errors"]))

    def test_invalid_aum_does_not_crash_aggregate_with_clean_holdings(self):
        # Holdings reconcile cleanly (would be MATCHED), but invalid AUM forces
        # the aggregate to INVALID_DATA without a crash.
        r = self._run(float("nan"))
        self.assertEqual(r["status"], STATUS_INVALID)
        # Holdings themselves remain MATCHED; only the aggregate is elevated.
        self.assertTrue(all(h["status"] == STATUS_MATCHED for h in r["holdings"]))


# --------------------------------------------------------------------------- #
# FIX 2 (v4) — integer-to-float overflow regression                            #
# --------------------------------------------------------------------------- #
class TestOverflowRegression(unittest.TestCase):
    """10**400 raises OverflowError on float() conversion. All numeric helpers
    must catch it and treat the value as invalid/unavailable, never valid, and
    never crash."""

    def test_validate_numeric_huge_positive_int_is_invalid(self):
        status, val, err = validate_numeric(10**400, "x")
        self.assertEqual(status, "invalid")
        self.assertIsNone(val)
        self.assertIn("too large", err.lower())

    def test_validate_numeric_huge_negative_int_is_invalid(self):
        status, val, err = validate_numeric(-(10**400), "x")
        self.assertEqual(status, "invalid")
        self.assertIsNone(val)

    def test_is_finite_number_huge_int_false(self):
        self.assertFalse(_is_finite_number(10**400))
        self.assertFalse(_is_finite_number(-(10**400)))

    def test_is_valid_number_huge_int_false(self):
        self.assertFalse(_is_valid_number(10**400))
        self.assertFalse(_is_valid_number(-(10**400)))

    def test_reconcile_holding_huge_quantity_does_not_crash(self):
        # A holding whose quantity overflows float must be INVALID_DATA, not a crash.
        h = reconcile_holding(_h("A", 10**400, 50.0, 0.5, cost_basis=5000.0))
        self.assertEqual(h["status"], STATUS_INVALID)
        self.assertIsNone(h["market_value"])

    def test_reconcile_holdings_huge_quantity_no_crash(self):
        r = _reconcile_holdings(
            [_h("A", 10**400, 50.0, 0.5, cost_basis=5000.0),
             _h("B", 100, 50.0, 0.5, cost_basis=5000.0)],
            1_000_000, "TestPortfolio")
        self.assertTrue(r["success"])
        self.assertEqual(r["status"], STATUS_INVALID)

    def test_comparison_winner_huge_int_unavailable(self):
        # A huge-int metric must be unavailable, not a crash and not an accidental tie.
        mv = {"total_return_1y": (10**400, 5), "sharpe_ratio": (2, 1)}
        d = _decide_overall_winner(mv, "P1", "P2")
        self.assertEqual(d["per_metric_winner"]["total_return_1y"], "unavailable")
        self.assertEqual(d["unavailable_count"], 1)

    def test_no_helper_crashes_on_overflow(self):
        # Exercise all three helpers; none should raise.
        validate_numeric(10**400, "x")
        _is_finite_number(10**400)
        _is_valid_number(10**400)


if __name__ == "__main__":
    unittest.main()
