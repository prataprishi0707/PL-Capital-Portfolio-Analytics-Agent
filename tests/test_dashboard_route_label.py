"""
Route-label tests for the AI Analyst page.

These tests call get_route_label() from dashboard/pl_theme.py directly —
the same function the dashboard page imports and calls.  This ensures
tests exercise the production code, not a disconnected mirror.
"""

import sys
import unittest
from pathlib import Path

# Add the dashboard directory so pl_theme is importable
DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))

from pl_theme import get_route_label


class TestGetRouteLabel(unittest.TestCase):
    """Tests against the actual get_route_label() function in pl_theme.py."""

    # ── Explicit metadata ─────────────────────────────────────────────────

    def test_offline_string_gives_offline_label(self):
        self.assertEqual(get_route_label("offline"),
                         "🔵 Offline deterministic route")

    def test_llm_string_gives_llm_label(self):
        self.assertEqual(get_route_label("llm"),
                         "🟣 Gemini LLM route")

    # ── Missing / unknown / empty → neutral ───────────────────────────────

    def test_none_gives_neutral_label(self):
        self.assertEqual(get_route_label(None), "🔧 Tool execution")

    def test_empty_string_gives_neutral_label(self):
        self.assertEqual(get_route_label(""), "🔧 Tool execution")

    def test_unknown_string_gives_neutral_label(self):
        self.assertEqual(get_route_label("hybrid"), "🔧 Tool execution")

    def test_integer_gives_neutral_label(self):
        self.assertEqual(get_route_label(1), "🔧 Tool execution")

    def test_bool_gives_neutral_label(self):
        self.assertEqual(get_route_label(True), "🔧 Tool execution")

    # ── Regression: must NOT infer from tool count ────────────────────────

    def test_single_tool_no_route_is_neutral_not_offline(self):
        """The old heuristic (single tool → offline) must not creep back."""
        label = get_route_label(None)
        self.assertNotEqual(label, "🔵 Offline deterministic route",
            msg="None route must not be labelled as offline routing")

    def test_multiple_tools_no_route_is_neutral_not_llm(self):
        """The old heuristic (multiple tools → LLM) must not creep back."""
        label = get_route_label(None)
        self.assertNotEqual(label, "🟣 Gemini LLM route",
            msg="None route must not be labelled as LLM routing")

    # ── Zero-tool-call scenario must not raise ────────────────────────────

    def test_zero_tool_response_does_not_raise(self):
        """Simulates a successful answer with no tool calls.
        route comes from response.get('route', '') = '' → neutral, no exception."""
        response = {"answer": "There are 13 portfolios.", "tool_calls": []}
        route = response.get("route", "")
        # This must not raise; it must return the neutral label
        label = get_route_label(route)
        self.assertEqual(label, "🔧 Tool execution")

    # ── Consistency: history replay and live path produce same label ───────

    def test_offline_label_consistent(self):
        """Simulate storing route='offline' in history, then replaying it."""
        stored = {"role": "assistant", "content": "x",
                  "tool_calls": [{}], "route": "offline"}
        replay_label = get_route_label(stored.get("route"))
        self.assertEqual(replay_label, "🔵 Offline deterministic route")

    def test_llm_label_consistent(self):
        stored = {"role": "assistant", "content": "x",
                  "tool_calls": [{}, {}], "route": "llm"}
        replay_label = get_route_label(stored.get("route"))
        self.assertEqual(replay_label, "🟣 Gemini LLM route")

    def test_missing_route_key_consistent(self):
        stored = {"role": "assistant", "content": "x", "tool_calls": [{}]}
        replay_label = get_route_label(stored.get("route"))
        self.assertEqual(replay_label, "🔧 Tool execution")


if __name__ == "__main__":
    unittest.main()
