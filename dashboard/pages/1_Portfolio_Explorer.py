
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))

from portfolio_health import analyze_portfolio_health

st.set_page_config(
    page_title="Portfolio Explorer | PL Capital",
    page_icon="🔎",
    layout="wide"
)

st.title("Portfolio Explorer")
st.caption("Explore portfolio composition, sector exposure and portfolio health.")

# Portfolio selection
from database import get_connection

conn = get_connection()

portfolios = pd.read_sql_query(
    "SELECT portfolio_id, portfolio_name FROM portfolios ORDER BY portfolio_name",
    conn
)

conn.close()

selected_portfolio = st.selectbox(
    "Select a Portfolio",
    portfolios["portfolio_name"].tolist()
)

# Backend analysis
result = analyze_portfolio_health(selected_portfolio)

if not result.get("success"):
    st.error(result.get("error", "Unable to analyze portfolio."))
    st.stop()

portfolio = result["portfolio"]
performance = result.get("performance") or {}
risk = result.get("risk_metrics") or {}

st.divider()

# Portfolio overview
st.subheader("Portfolio Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total AUM", f"₹{portfolio['total_aum']:,.0f}")
c2.metric("Strategy", portfolio["strategy_type"])
c3.metric("Target Risk", portfolio["target_risk_level"])
c4.metric("Status", portfolio["status"])

st.caption(
    f"Benchmark: {portfolio.get('benchmark_index', 'N/A')} | "
    f"Analysis status: {result['analysis_status']}"
)

st.divider()

# Asset allocation
st.subheader("Asset Allocation")

asset_data = result.get("asset_allocation", [])

if asset_data:
    allocation_df = pd.DataFrame(asset_data)

    allocation_chart = px.pie(
        allocation_df,
        names="asset_type",
        values="allocation_percentage",
        hole=0.5,
        title="Portfolio Asset Composition"
    )

    left, right = st.columns([1, 1])

    with left:
        st.plotly_chart(allocation_chart, width="stretch")

    with right:
        st.dataframe(
            allocation_df,
            width="stretch",
            hide_index=True
        )

else:
    st.info("No asset allocation records available.")

st.caption(
    f"Unallocated total portfolio allocation: "
    f"{result.get('unallocated_allocation', 0):.2f}%"
)

st.divider()

# Sector exposure
st.subheader("Sector Exposure")

sector_data = result.get("sector_exposures", [])

if sector_data:
    sector_df = pd.DataFrame(sector_data)

    fig = px.bar(
        sector_df,
        x="sector_name",
        y="exposure_percentage",
        color="sector_name",
        text="exposure_percentage",
        title="Sector-wise Equity Exposure"
    )

    fig.update_layout(
        xaxis_title="Sector",
        yaxis_title="Exposure (%)",
        showlegend=False
    )

    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        sector_df,
        width="stretch",
        hide_index=True
    )

else:
    st.info("No sector exposure data available.")

# Concentration analysis
concentration = result.get("sector_concentration", {})

c1, c2, c3 = st.columns(3)

c1.metric(
    "Sector HHI",
    f"{concentration.get('hhi', 0):.3f}"
)

c2.metric(
    "Effective Number of Sectors",
    f"{concentration.get('effective_number_of_sectors', 0):.2f}"
)

largest_sector = concentration.get("largest_sector") or {}

c3.metric(
    "Largest Sector",
    largest_sector.get("sector_name", "N/A"),
    f"{largest_sector.get('exposure_percentage', 0):.1f}% exposure"
)

st.divider()

# Performance metrics
st.subheader("Performance Overview")

if performance:
    p1, p2, p3, p4 = st.columns(4)

    p1.metric("1M Return", f"{performance['total_return_1m']:.2f}%")
    p2.metric("3M Return", f"{performance['total_return_3m']:.2f}%")
    p3.metric("1Y Return", f"{performance['total_return_1y']:.2f}%")
    p4.metric("Sharpe Ratio", f"{performance['sharpe_ratio']:.2f}")

    st.caption(
        f"Performance data date: {performance.get('performance_date', 'N/A')}"
    )
else:
    st.info("Performance data is unavailable for this portfolio.")

st.divider()

# Risk metrics
st.subheader("Risk Indicators")

if risk:
    r1, r2, r3, r4 = st.columns(4)

    r1.metric("Beta", f"{risk['beta']:.2f}")
    r2.metric("VaR 95%", f"{risk['var_95']:.2f}%")
    r3.metric("Volatility", f"{performance.get('volatility', 0):.2f}%")
    r4.metric("Max Drawdown", f"{performance.get('max_drawdown', 0):.2f}%")

    st.caption(
        f"Risk calculation date: {risk.get('calculation_date', 'N/A')}"
    )
else:
    st.info("Risk metrics are unavailable for this portfolio.")

st.divider()

# Risk alerts
st.subheader("Portfolio Alerts")

alerts = result.get("alerts", [])

if alerts:
    for alert in alerts:
        severity = alert.get("severity", "medium").lower()

        if severity == "high":
            st.error(alert["message"])
        elif severity == "medium":
            st.warning(alert["message"])
        else:
            st.info(alert["message"])
else:
    st.success("No portfolio risk alerts identified.")

# Data quality
quality_alerts = result.get("data_quality_alerts", [])

st.subheader("Data Quality")

if quality_alerts:
    for alert in quality_alerts:
        st.warning(alert.get("message", str(alert)))
else:
    st.success("No data quality alerts reported.")

st.caption(result.get("thresholds_note", ""))

st.warning(
    result.get(
        "data_note",
        "Metrics are based on the supplied historical dataset, not live market data."
    )
)
