# PL Capital — AI Portfolio Analytics Agent

An AI-powered portfolio analytics system that translates natural-language questions into database queries, calculates sector exposures, and provides portfolio health, risk and reconciliation insights through an interactive dashboard.

## 1. Project Overview

The **PL Capital AI Portfolio Analytics Agent** makes portfolio data easier to query and understand.

Users ask questions in natural language. The AI agent selects and executes the appropriate analytical tool, combining Gemini function calling, a deterministic offline router, SQLite database operations and Python-based financial analytics.

The project implements six analytical tools, a hybrid routing architecture, portfolio reconciliation, a six-page Streamlit dashboard, and a comprehensive automated test suite.

## 2. Key Features

### AI-Powered Querying
- Converts natural-language questions into SQL queries or tool calls.
- Uses a **hybrid routing architecture**: deterministic offline rules for high-confidence patterns, Gemini function calling for complex or ambiguous queries.
- Maintains conversation history.
- Tool execution details are visible and inspectable.

### Sector Exposure Calculator
- Calculates sector-wise portfolio equity exposure from holding weights and security-sector mappings.
- Excludes bond holdings. Reports sector exposure percentages.

### Portfolio Health Analysis
- Computes a documented health score (0–100) based on risk alerts, HHI concentration, and data availability.
- Returns health tier: healthy (≥80), moderate (55–79), needs attention (<55).
- Identifies risk and data-quality alerts.

### Risk Intelligence
- Computes a documented risk score (0–100, lower = more risk).
- Returns risk tier capped by the authoritative signal level: a high risk alert always forces "aggressive" tier regardless of numeric score.
- Reports data completeness percentage and assessment confidence.
- Never hides a high risk signal behind a high score.

### Portfolio Comparison
- Compares nine performance and risk metrics with documented winner logic.
- A winner requires ≥60% metric coverage, ≥4 comparable metrics, and a win margin ≥2.
- Returns `no_defensible_winner` when evidence is insufficient.
- Distinguishes actual zero from unavailable data in allocation and sector comparisons.

### Portfolio Reconciliation
- Reconciles recorded holding weights against market-value-computed weights.
- Partial denominators are never normalised: if any holding is missing a price or quantity, no holding receives a computed weight.
- Returns explicit statuses: MATCHED, OBSERVATION, DISCREPANCY_FOUND, INCOMPLETE, INVALID_DATA.
- Distinguishes missing AUM from invalid AUM.
- Provides a cost-basis diagnostic comparison.

### Interactive Dashboard
Six Streamlit pages:

| Page | Description |
|---|---|
| **Executive Overview** | Portfolio count, AUM, health distribution, Beta alerts, risk table |
| **Portfolio Explorer** | Holdings, allocation, sector exposure, performance and risk metrics |
| **Risk Intelligence** | Risk score, tier, signal, confidence, data completeness |
| **Portfolio Comparison** | Side-by-side comparison with coverage and winner/no-winner logic |
| **AI Analyst** | Natural-language conversational interface with tool visibility |
| **Reconciliation** | Weight drift, allocation drift, AUM coverage, validation errors |

## 3. System Architecture

```
User Query → AI Analyst
               ↓
    Hybrid Router
    ├─ Deterministic (offline): exact/partial match → tool
    └─ Gemini LLM: ambiguous → model selects tool
               ↓
    ┌────────────────────────────────────────────┐
    │              6 Analytical Tools            │
    │  SQL · Exposure · Health · Risk            │
    │  Comparison · Reconciliation               │
    └────────────────────────────────────────────┘
               ↓
    SQLite (read-only, authorizer-protected)
               ↓
    Structured result → Dashboard display
```

### Agent Tools

| Tool | Responsibility |
|---|---|
| `run_sql_query` | Validated, read-only SQL SELECT queries |
| `calculate_sector_exposure` | Equity sector exposures per portfolio |
| `analyze_portfolio_health` | Portfolio health score and alerts |
| `analyze_portfolio_risk` | Risk score, tier, signal, completeness |
| `compare_portfolios` | Coverage-aware two-portfolio comparison |
| `reconcile_portfolio` | Holding weight reconciliation and drift analysis |

## 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Application development |
| Google Gemini API | AI reasoning and function calling |
| google-genai SDK | Gemini API integration |
| SQLite | Portfolio database |
| Pandas | Data processing |
| Plotly | Interactive visualizations |
| Streamlit | Dashboard |
| Pytest | Automated testing |

## 5. Project Structure

```
PL-Capital-Portfolio-Analytics-Agent/
│
├── dashboard/
│   ├── app.py                        # Executive Overview
│   ├── pl_theme.py                   # Shared theme, CSS, utilities
│   └── pages/
│       ├── 1_Portfolio_Explorer.py
│       ├── 2_Risk_Intelligence.py
│       ├── 3_Portfolio_Comparison.py
│       ├── 4_AI_Analyst.py
│       └── 5_Reconciliation.py
│
├── data/
│   ├── benchmarks.csv
│   ├── historical_prices.csv
│   ├── holdings.csv
│   ├── portfolio_performance.csv
│   ├── portfolios.csv
│   ├── risk_metrics.csv
│   ├── sectors.csv
│   ├── securities.csv
│   └── transactions.csv
│
├── src/
│   ├── agent.py                      # AI orchestrator
│   ├── cache.py                      # TTL cache
│   ├── database.py                   # Read-only SQL with authorizer
│   ├── evaluator.py                  # Ground-truth evaluator
│   ├── exposure_calculator.py        # Sector exposure
│   ├── logger.py                     # Structured JSON logger
│   ├── main.py                       # CLI entry point
│   ├── portfolio_comparison.py       # Coverage-aware comparison
│   ├── portfolio_health.py           # Health score
│   ├── reconciliation.py             # Weight reconciliation
│   ├── risk_analyzer.py              # Risk score and tier
│   ├── router.py                     # Deterministic routing
│   ├── run_evaluation.py             # Evaluation runner
│   └── sql_tool.py                   # SQL generation
│
├── tests/
│   ├── test_backend.py               # 18 core backend tests
│   ├── test_hybrid_router.py         # 10 routing tests
│   ├── test_sql_security.py          # 8 SQL security tests
│   ├── test_evaluation.py            # 8 offline evaluation tests
│   ├── test_reconciliation.py        # 10 reconciliation tests
│   ├── test_enhanced_analytics.py    # 17 analytics tests
│   ├── test_adversarial.py           # 94 adversarial tests
│   └── test_dashboard_route_label.py # 13 route-label tests
│
├── portfolio_database.db             # SQLite — 13 portfolios, 9 tables
├── database_schema.sql
├── ground_truth_dataset.json         # 10-question evaluation dataset
├── requirements.txt
├── run_tests.py                      # Portable test runner
├── verify_protected_files.py         # SHA-256 integrity checker
├── reconciliation_report.txt         # Full 13-portfolio reconciliation
├── CHANGELOG.md
├── FINAL_VERIFICATION.md
└── DEMO_GUIDE.md
```

## 6. Database and Data

The project uses SQLite with nine tables: portfolios, sectors, securities, holdings, transactions, benchmarks, historical_prices, portfolio_performance, risk_metrics.

The SQL execution layer uses:
- Read-only URI mode (`file:...?mode=ro`)
- `PRAGMA query_only = ON`
- A custom authorizer that denies all non-SELECT operations and restricts reads to the nine allowed tables
- Query length, result-row and opcode limits

## 7. Installation and Configuration

### Prerequisites
- Python 3.10 or later
- Google AI Studio API key (optional — offline mode works without it)

### Step 1: Clone the repository
```bash
git clone https://github.com/prataprishi0707/PL-Capital-Portfolio-Analytics-Agent.git
cd PL-Capital-Portfolio-Analytics-Agent
```

### Step 2: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure the Gemini API key (optional)
```bash
# Windows
set GOOGLE_API_KEY=your_key_here

# Linux / macOS
export GOOGLE_API_KEY=your_key_here
```

Set `GEMINI_MODEL` to override the default model (gemini-2.5-flash).

Do not commit API keys to the repository.

### Step 4: Launch the dashboard
```bash
python -m streamlit run dashboard/app.py
```

The dashboard opens at `http://localhost:8501`.

### Step 5: Run CLI agent (optional)
```bash
python src/main.py --question "How many portfolios are in the database?"
```

## 8. Running Tests

```bash
# Portable unittest runner (Windows-compatible)
python run_tests.py

# pytest
python -m pytest tests/ -q
```

**178 tests pass.** Breakdown:

| File | Tests |
|---|---|
| test_backend.py | 18 |
| test_hybrid_router.py | 10 |
| test_sql_security.py | 8 |
| test_evaluation.py | 8 |
| test_reconciliation.py | 10 |
| test_enhanced_analytics.py | 17 |
| test_adversarial.py | 94 |
| test_dashboard_route_label.py | 13 |
| **Total** | **178** |

## 9. Agent Evaluation

```bash
python src/run_evaluation.py
```

Requires `GOOGLE_API_KEY`. Evaluates tool selection and SQL accuracy against `ground_truth_dataset.json`.

Offline evaluation (no API key) tests the evaluator infrastructure and both exposure questions: `python -m pytest tests/test_evaluation.py -v`.

## 10. Verified Capabilities

| Capability | Status |
|---|---|
| SQL read-only security (INSERT/UPDATE/DELETE/DROP rejected) | ✅ Verified |
| Sector exposure calculator | ✅ Verified |
| Portfolio health with documented score formula | ✅ Verified |
| Risk score capped by authoritative signal level | ✅ Verified |
| Coverage-aware comparison with documented thresholds | ✅ Verified |
| Partial-denominator reconciliation (never normalises incomplete data) | ✅ Verified |
| Invalid AUM distinguished from missing AUM | ✅ Verified |
| Overflow safety in all three numeric helpers | ✅ Verified |
| Offline deterministic routing (no API key needed) | ✅ Verified |
| Streamlit dashboard startup (HTTP 200) | ✅ Verified |
| Full browser UI interaction | ⚠️ Not independently verified |
| Live Gemini API evaluation | ⚠️ Requires GOOGLE_API_KEY |

## 11. Known Limitations

- **Live Gemini evaluation**: The 10-question ground-truth evaluation requires a valid `GOOGLE_API_KEY`. The offline evaluation infrastructure passes 8/8 offline checks.
- **Browser interaction**: Streamlit HTTP 200 is confirmed. Full chart rendering, dropdown interaction and AI Analyst conversation flow require manual browser testing.
- **Reconciliation discrepancies**: 12/13 portfolios show `DISCREPANCY_FOUND` because `current_price` in the securities table has moved since `current_weight` was calibrated. This is a property of the static historical dataset and is reported honestly.
- **Risk score boundary**: The numeric score thresholds and alert thresholds are independently calibrated. At exact boundaries they can differ, but the authoritative signal-capping mechanism ensures a high alert always forces `aggressive` tier.
- **Historical data**: All metrics are sourced from the supplied historical assessment dataset. The system is not connected to live market prices or portfolio feeds.

## 12. Security Properties

- All SQL queries are validated before execution.
- Only SELECT and WITH (CTE) statements are permitted.
- An authorizer restricts table access to the nine named tables.
- The `GOOGLE_API_KEY` is read from an environment variable only — never hardcoded.
- No credentials, API keys or `.env` files are committed to the repository.
