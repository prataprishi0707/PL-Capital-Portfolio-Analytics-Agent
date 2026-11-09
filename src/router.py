"""
PL Capital Hybrid Query Router Module.
Provides offline, high-confidence deterministic routing for portfolio analytical queries,
with fallback to Google Gemini for complex or ambiguous phrasing.

Canonical portfolio names are verified against the actual database:
  SELECT portfolio_name FROM portfolios ORDER BY portfolio_id;
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Canonical portfolio names - verified directly from the database
# SELECT portfolio_name FROM portfolios ORDER BY portfolio_id;
CANONICAL_PORTFOLIOS = [
    "Growth Equity Fund",
    "Conservative Income Fund",
    "Tech Innovation Fund",
    "Balanced Portfolio",
    "ESG Sustainable Fund",
    "Small Cap Value Fund",
    "International Equity Fund",
    "Fixed Income Plus",
    "Dividend Aristocrats Fund",
    "Emerging Markets Fund",
    "Total Stock Market Index Fund",
    "Total Bond Market Index Fund",
    "Total International Index Fund",
]


@dataclass
class RoutingResult:
    confidence: float
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    trace: List[str] = field(default_factory=list)


def extract_portfolio_entity(text: str) -> tuple[Optional[str], List[str]]:
    """Extracts portfolio names matching canonical portfolios (with short-form support)."""
    trace = []
    text_lower = text.lower().strip()

    # Try exact match first
    for p in CANONICAL_PORTFOLIOS:
        if p.lower() in text_lower:
            trace.append(f"Exact canonical portfolio match: {p}")
            return p, trace

    # Try short-form / partial matching
    # Stop-words to exclude from matching to avoid false positives
    STOP_WORDS = {
        "fund", "portfolio", "equity", "income", "opportunities",
        "index", "market", "total", "international",
    }
    best_match = None
    best_score = 0
    for p in CANONICAL_PORTFOLIOS:
        p_words = set(re.findall(r'\w+', p.lower())) - STOP_WORDS
        if not p_words:
            continue
        match_count = sum(1 for w in p_words if w in text_lower)
        if match_count > best_score and match_count > 0:
            best_match = p
            best_score = match_count

    if best_match:
        trace.append(f"Partial portfolio match: {best_match} (score: {best_score})")
        return best_match, trace

    return None, trace


def route_query(user_question: str) -> RoutingResult:
    """Offline routing engine matching query structures deterministically."""
    trace = ["Starting hybrid offline routing analysis."]
    q = user_question.strip().lower()

    # 1. Total Portfolio Count
    if re.search(r'\bhow many portfolios\b', q) or re.search(r'\btotal\s+number\s+of\s+portfolios\b', q):
        trace.append("Matched Total Portfolio Count rule.")
        return RoutingResult(
            confidence=1.0,
            tool_name="run_sql_query",
            arguments={"query": "SELECT COUNT(*) FROM portfolios;"},
            trace=trace
        )

    # 2. Names of Active Portfolios
    if re.search(r'\bnames\s+of\s+all\s+active\s+portfolios\b', q) or ("active portfolios" in q and "names" in q):
        trace.append("Matched Active Portfolios List rule.")
        return RoutingResult(
            confidence=1.0,
            tool_name="run_sql_query",
            arguments={"query": "SELECT portfolio_name FROM portfolios WHERE LOWER(status) = 'active';"},
            trace=trace
        )

    # 3. Technology Sector Securities
    if "securities" in q and "technology sector" in q:
        trace.append("Matched Sector Securities query pattern.")
        return RoutingResult(
            confidence=1.0,
            tool_name="run_sql_query",
            arguments={"query": (
                "SELECT s.symbol, s.company_name "
                "FROM securities s "
                "JOIN sectors sec ON s.sector_id = sec.sector_id "
                "WHERE sec.sector_name = 'Technology';"
            )},
            trace=trace
        )

    # 4. Sector Exposure Calculator
    if any(phrase in q for phrase in ["sector exposure", "sector breakdown", "sector allocation"]):
        portfolio, p_trace = extract_portfolio_entity(q)
        trace.extend(p_trace)
        if portfolio:
            trace.append(f"High-confidence sector exposure route for: {portfolio}")
            return RoutingResult(
                confidence=1.0,
                tool_name="calculate_sector_exposure",
                arguments={"portfolio_name": portfolio},
                trace=trace
            )

    # 5. Portfolio Risk Analysis
    if any(phrase in q for phrase in ["risk intelligence", "risk analysis", "var", "beta", "risk assessment"]) and "compare" not in q:
        portfolio, p_trace = extract_portfolio_entity(q)
        trace.extend(p_trace)
        if portfolio:
            trace.append(f"High-confidence portfolio risk analysis route for: {portfolio}")
            return RoutingResult(
                confidence=1.0,
                tool_name="analyze_portfolio_risk",
                arguments={"portfolio_name": portfolio},
                trace=trace
            )

    # 6. Portfolio Health Analysis
    if any(phrase in q for phrase in ["portfolio health", "health analysis", "health check", "health score"]) and "compare" not in q:
        portfolio, p_trace = extract_portfolio_entity(q)
        trace.extend(p_trace)
        if portfolio:
            trace.append(f"High-confidence portfolio health route for: {portfolio}")
            return RoutingResult(
                confidence=1.0,
                tool_name="analyze_portfolio_health",
                arguments={"portfolio_name": portfolio},
                trace=trace
            )

    # 7. Reconciliation
    if any(phrase in q for phrase in ["reconcil", "weight drift", "holdings check", "holdings reconcil"]):
        portfolio, p_trace = extract_portfolio_entity(q)
        trace.extend(p_trace)
        if portfolio:
            trace.append(f"High-confidence reconciliation route for: {portfolio}")
            return RoutingResult(
                confidence=1.0,
                tool_name="reconcile_portfolio",
                arguments={"portfolio_name": portfolio},
                trace=trace
            )

    # 8. Portfolio Comparison
    if "compare" in q:
        extracted_ports = []
        for p in CANONICAL_PORTFOLIOS:
            if p.lower() in q:
                extracted_ports.append(p)
        if len(extracted_ports) == 2:
            trace.append(
                f"High-confidence portfolio comparison route for: "
                f"{extracted_ports[0]} and {extracted_ports[1]}"
            )
            return RoutingResult(
                confidence=1.0,
                tool_name="compare_portfolios",
                arguments={
                    "portfolio_name_1": extracted_ports[0],
                    "portfolio_name_2": extracted_ports[1],
                },
                trace=trace
            )

    # Default: low-confidence fallback to LLM agent routing
    trace.append("No offline rule matched with high confidence. Falling back to Gemini LLM Agent Router.")
    return RoutingResult(confidence=0.0, trace=trace)
