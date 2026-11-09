# PL Capital Portfolio Analytics Agent — Demonstration Guide

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key (optional — offline mode works without it)
set GOOGLE_API_KEY=your_key_here          # Windows CMD
# export GOOGLE_API_KEY=your_key_here    # Linux / macOS

# Launch the dashboard
python -m streamlit run dashboard/app.py

# Run the test suite
python run_tests.py
```

The dashboard opens at **http://localhost:8501**

---

## Recommended Demonstration Sequence

### 1. Executive Overview (first 30 seconds)
Open the dashboard. The Overview page loads automatically and shows:
- 13 portfolios with ₹329.5M total AUM
- Portfolio health distribution (healthy / moderate / needs attention)
- AUM distribution by portfolio
- Beta Alerts count (portfolios with Beta > 1.2)
- Risk metrics overview table

Point out: **"Beta Alerts is a single-threshold indicator, not the full risk engine."**

---

### 2. Portfolio Explorer — contrast two portfolios
Select **Tech Innovation Fund** → show:
- Health score 40/100 (Needs Attention) — driven by 3 high risk alerts
- 100% Technology sector concentration
- Holdings table with quantities, prices and weights

Then select **Conservative Income Fund** → show:
- Bond-heavy allocation (visible in donut chart)
- No equity sector exposure (bonds-only → no sector data, explicit N/A)
- Performance and risk data present; individual None fields show "N/A" not "0.00"

Point out: **"Missing values are explicitly marked N/A — we do not substitute zero."**

---

### 3. Risk Intelligence — signal vs score contrast
Select **Balanced Portfolio**:
- risk_score = 100/100 (all metrics within normal ranges)
- risk_level = high (one alert: beta > 1.2)
- risk_tier = **aggressive** (capped by signal — score cannot hide the alert)

Point out: **"The score says 100 but the tier is Aggressive because the risk signal is authoritative. A high score cannot hide a high alert."**

---

### 4. Portfolio Comparison — coverage-aware winner
Compare **Tech Innovation Fund** vs **Growth Equity Fund**:
- 9/9 metrics comparable, 100% coverage
- Growth Equity Fund wins on 6 of 9 metrics (lower risk profile)
- Winner declared with explicit reason and threshold display

Then compare **Total Bond Market Index Fund** vs **Fixed Income Plus**:
- 0/9 metrics comparable (both are holdings-only portfolios with no perf/risk records)
- Result: **No Defensible Winner** — coverage insufficient, no fabricated result

Point out: **"We show 'No Defensible Winner' rather than forcing a false result."**

---

### 5. AI Analyst — live questions
*(Requires GOOGLE_API_KEY; Demo Mode works offline for these questions)*

**Easy questions (offline routing — no API key needed):**
- "How many portfolios are in the database?"  → SQL tool, answer: 13
- "What are the sector exposures for the Tech Innovation Fund?"  → Sector exposure tool
- "Analyze the health of the Balanced Portfolio."  → Portfolio health tool
- "Compare Tech Innovation Fund and Growth Equity Fund."  → Comparison tool

**Questions requiring Gemini (need API key):**
- "Which portfolio has the highest Sharpe ratio?"  → SQL + aggregation
- "List the top 5 holdings by cost basis in the Growth Equity Fund."  → SQL with ORDER BY
- "What is the total AUM of all high-risk portfolios?"  → SQL with WHERE filter

Point out: **"Tool execution details are shown below each response. SQL is validated as read-only before execution."**

---

### 6. Reconciliation — complete audit
Select **Tech Innovation Fund** → click Run Reconciliation:
- Status: DISCREPANCY_FOUND (all 13 portfolios show this)
- Denominator complete: market-value weights computed for all 8 holdings
- Allocation drift: weights sum to 1.0 exactly (MATCHED)
- AUM coverage: ~4.9% (market value ÷ recorded AUM — informational only)

Explain: **"The discrepancy is because current_price has moved since the weights were calibrated. We report it honestly rather than suppressing it."**

---

## Key Talking Points for Judges

### Technical depth
- 14 backend source files with strict read-only SQL security
- 6-tool AI agent (SQL, sector exposure, health, risk, comparison, reconciliation)
- Hybrid routing: deterministic offline + Gemini fallback
- Strict numeric validation (NaN, infinity, overflow, null all handled)
- 178 automated tests across 8 test files

### Financial credibility
- Risk tier is capped by the authoritative signal level — a high signal cannot be hidden by a high numeric score
- No-defensible-winner outcome when comparison coverage is < 60% or < 4 comparable metrics
- Partial reconciliation denominators are never normalised
- Missing metrics display as "N/A" not "0.00"

### Engineering discipline
- All protected files byte-for-byte identical to original dataset (SHA-256 verified)
- Backend frozen and independently verified across v1–v4 and final release
- Single source of truth for route-label logic (`pl_theme.get_route_label`)
- Tests call production functions directly, not mirrors

### Honest limitations
- Gemini live evaluation requires API key (not available in demo environment)
- Browser UI requires manual testing (HTTP 200 confirmed programmatically)
- Reconciliation discrepancies are a dataset property, not data corruption

---

## Architecture Summary

```
User Query → AI Analyst Page
               ↓
          ask_portfolio_agent()
               ↓
    [Deterministic Router]         [Gemini LLM Router]
    exact/partial match → tool     ambiguous → Gemini selects tool
               ↓                               ↓
    ┌──────────────────────────────────────────┐
    │           6 Analytical Tools             │
    │  SQL · Exposure · Health · Risk          │
    │  Comparison · Reconciliation             │
    └──────────────────────────────────────────┘
               ↓
    SQLite (read-only, authorizer-protected)
               ↓
    Structured result → Dashboard display
```

---

## File Manifest

| Path | Purpose |
|---|---|
| `src/agent.py` | AI orchestrator with hybrid routing |
| `src/database.py` | Read-only SQL with security authorizer |
| `src/router.py` | Deterministic offline query router |
| `src/portfolio_health.py` | Health score + alerts |
| `src/risk_analyzer.py` | Risk score, tier, signal |
| `src/portfolio_comparison.py` | Coverage-aware comparison |
| `src/reconciliation.py` | Weight drift + partial-denominator safety |
| `src/exposure_calculator.py` | Sector exposure |
| `dashboard/app.py` | Executive Overview |
| `dashboard/pl_theme.py` | Shared theme, CSS, utilities |
| `dashboard/pages/1_Portfolio_Explorer.py` | Per-portfolio deep dive |
| `dashboard/pages/2_Risk_Intelligence.py` | Risk signal + score |
| `dashboard/pages/3_Portfolio_Comparison.py` | Side-by-side comparison |
| `dashboard/pages/4_AI_Analyst.py` | AI chat interface |
| `dashboard/pages/5_Reconciliation.py` | Holdings reconciliation |
| `tests/` | 178 automated tests across 8 files |
| `portfolio_database.db` | SQLite — 13 portfolios, 9 tables |
| `ground_truth_dataset.json` | 10-question evaluation dataset |
