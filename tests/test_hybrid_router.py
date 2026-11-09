"""
PL Capital Hybrid Router Offline Verification Suite.
Verifies deterministic routing scenarios, partial entity extraction, and confidence mapping.
"""

import unittest
from router import route_query, RoutingResult, extract_portfolio_entity

class TestHybridRouter(unittest.TestCase):

    def test_total_portfolio_count(self):
        """Scenario 1: Verify 'how many portfolios' maps to SQL count query with 1.0 confidence."""
        res = route_query("How many portfolios do we have in total?")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "run_sql_query")
        self.assertIn("COUNT(*)", res.arguments["query"])

    def test_active_portfolios_list(self):
        """Scenario 2: Verify active portfolios query maps to SQL query filtering for active status."""
        res = route_query("What are the names of all active portfolios?")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "run_sql_query")
        self.assertIn("active", res.arguments["query"].lower())

    def test_tech_sector_securities(self):
        """Scenario 3: Verify technology sector query maps to SQL list of securities."""
        res = route_query("Which securities are in the Technology sector?")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "run_sql_query")
        self.assertIn("Technology", res.arguments["query"])

    def test_exact_canonical_sector_exposure(self):
        """Scenario 4: Verify exact portfolio name matches and maps to sector exposure calculator."""
        res = route_query("Show me the sector exposure for Tech Innovation Fund")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "calculate_sector_exposure")
        self.assertEqual(res.arguments["portfolio_name"], "Tech Innovation Fund")

    def test_short_form_sector_exposure(self):
        """Scenario 5: Verify partial/shortened portfolio name matches to the canonical name."""
        res = route_query("What is the sector allocation for tech innovation?")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "calculate_sector_exposure")
        self.assertEqual(res.arguments["portfolio_name"], "Tech Innovation Fund")

    def test_short_form_risk_analyzer(self):
        """Scenario 6: Verify shortened name with risk-related query maps to portfolio risk tool.
        
        Uses 'dividend' as the partial match keyword.
        Verified against DB: the only portfolio with 'dividend' in its name is
        'Dividend Aristocrats Fund' (portfolio_id=9).
        """
        res = route_query("Show me risk analysis for dividend yield")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "analyze_portfolio_risk")
        # 'Dividend Yield Portfolio' does not exist in the database.
        # The actual matching portfolio is 'Dividend Aristocrats Fund'.
        self.assertEqual(res.arguments["portfolio_name"], "Dividend Aristocrats Fund")

    def test_portfolio_comparison(self):
        """Scenario 7: Verify two named portfolios map successfully to compare portfolios tool.
        
        Uses actual portfolio names verified against the database.
        'ESG Leaders Portfolio' and 'Global Macro Fund' do not exist in the DB.
        Replaced with 'ESG Sustainable Fund' (portfolio_id=5) and
        'Emerging Markets Fund' (portfolio_id=10), both confirmed in DB.
        """
        res = route_query("Compare ESG Sustainable Fund and Emerging Markets Fund")
        self.assertEqual(res.confidence, 1.0)
        self.assertEqual(res.tool_name, "compare_portfolios")
        self.assertEqual(res.arguments["portfolio_name_1"], "ESG Sustainable Fund")
        self.assertEqual(res.arguments["portfolio_name_2"], "Emerging Markets Fund")

    def test_ambiguous_query_fallback(self):
        """Scenario 8: Verify completely random/ambiguous phrasing gracefully falls back with 0.0 confidence."""
        res = route_query("What is the weather in Delhi tomorrow?")
        self.assertEqual(res.confidence, 0.0)
        self.assertIsNone(res.tool_name)
        self.assertIn("No offline rule matched", res.trace[-1])

    def test_partially_ambiguous_portfolio_risk_fallback(self):
        """Scenario 9: Verify risk queries with missing or unrecognizable portfolios fall back to LLM."""
        res = route_query("Calculate the VaR and Beta for some random fund")
        self.assertEqual(res.confidence, 0.0)
        self.assertIsNone(res.tool_name)

    def test_diagnostic_traces_populated(self):
        """Scenario 10: Verify that diagnostic traces are appended step-by-step for testing transparency."""
        res = route_query("Show me the sector exposure for the Emerging Markets Fund")
        self.assertTrue(len(res.trace) > 1)
        self.assertTrue(any("Starting hybrid" in t for t in res.trace))
        self.assertTrue(any("High-confidence" in t for t in res.trace))

if __name__ == '__main__':
    unittest.main()
