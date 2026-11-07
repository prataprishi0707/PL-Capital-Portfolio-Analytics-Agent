
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))

from risk_analyzer import analyze_portfolio_risk
from database import get_connection


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Risk Intelligence | PL Capital",
    page_icon="🛡️",
    layout="wide"
)

st.title("Risk Intelligence")
st.caption(
    "Portfolio risk assessment, market sensitivity, "
    "downside risk and risk alerts."
)


# --------------------------------------------------
# PORTFOLIO SELECTION
# --------------------------------------------------

conn = get_connection()

portfolios = pd.read_sql_query(
    "SELECT portfolio_name FROM portfolios ORDER BY portfolio_name",
    conn
)

conn.close()

if portfolios.empty:
    st.error("No portfolios found in the database.")
    st.stop()

selected_portfolio = st.selectbox(
    "Select Portfolio",
    portfolios["portfolio_name"].tolist()
)

result = analyze_portfolio_risk(selected_portfolio)

if not result.get("success"):
    st.error(result.get("error", "Risk analysis failed."))
    st.stop()

risk_level = result.get("risk_level", "not_assessed")
indicators = result.get("risk_indicators") or {}

available = result.get("available_metrics", [])
unavailable = result.get("unavailable_metrics", [])


# --------------------------------------------------
# OVERALL RISK CLASSIFICATION
# --------------------------------------------------

st.divider()

st.subheader("Overall Risk Classification")

risk_colors = {
    "high": "🔴",
    "moderate": "🟠",
    "lower_observed_signals": "🟢",
    "not_assessed": "⚪"
}

risk_label = risk_level.replace("_", " ").title()

st.markdown(
    f"## {risk_colors.get(risk_level, '⚪')} {risk_label}"
)

st.caption(
    f"Analysis Status: "
    f"{result.get('analysis_status', 'unknown').replace('_', ' ').title()}"
)

st.divider()


# --------------------------------------------------
# KEY RISK INDICATORS
# --------------------------------------------------

st.subheader("Key Risk Indicators")

metric_config = [
    ("beta", "Beta", ""),
    ("var_95", "VaR 95%", "%"),
    ("var_99", "VaR 99%", "%"),
    ("volatility", "Volatility", "%"),
    ("max_drawdown", "Maximum Drawdown", "%"),
    ("sharpe_ratio", "Sharpe Ratio", ""),
    ("sortino_ratio", "Sortino Ratio", ""),
    ("cvar_95", "CVaR 95%", "%"),
    ("tracking_error", "Tracking Error", "%")
]

for start in range(0, len(metric_config), 3):

    columns = st.columns(3)

    for column, (key, label, suffix) in zip(
        columns,
        metric_config[start:start + 3]
    ):

        if key in available and key in indicators:

            value = indicators[key].get("value")

            with column:
                st.metric(
                    label,
                    f"{value:.2f}{suffix}"
                    if value is not None else "N/A"
                )

        else:

            with column:
                st.metric(label, "N/A")


st.divider()


# --------------------------------------------------
# RISK METRICS VISUALIZATION
# --------------------------------------------------

st.subheader("Risk Metrics Analysis")


# 1. MARKET SENSITIVITY

st.markdown("#### Market Sensitivity")

beta_col, volatility_col = st.columns(2)

if "beta" in available and indicators.get("beta"):

    beta_col.metric(
        "Portfolio Beta",
        f"{indicators['beta']['value']:.2f}",
        help="Measures sensitivity to market movements."
    )

else:
    beta_col.metric("Portfolio Beta", "N/A")


if "volatility" in available and indicators.get("volatility"):

    volatility_col.metric(
        "Portfolio Volatility",
        f"{indicators['volatility']['value']:.2f}%",
        help="Historical portfolio volatility."
    )

else:
    volatility_col.metric("Portfolio Volatility", "N/A")


st.divider()


# 2. DOWNSIDE RISK

st.markdown("#### Downside Risk")

downside_keys = [
    ("var_95", "VaR 95%"),
    ("var_99", "VaR 99%"),
    ("cvar_95", "CVaR 95%"),
    ("max_drawdown", "Maximum Drawdown")
]

downside_data = [
    {
        "Indicator": label,
        "Value": indicators[key]["value"]
    }
    for key, label in downside_keys
    if key in available
    and key in indicators
    and indicators[key].get("value") is not None
]

if downside_data:

    downside_df = pd.DataFrame(downside_data)

    fig = px.bar(
        downside_df,
        x="Indicator",
        y="Value",
        text="Value",
        color="Indicator",
        title="Portfolio Downside Risk (%)"
    )

    fig.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside"
    )

    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Percentage (%)",
        margin=dict(t=60, b=30),
        height=380
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:

    st.info("Downside risk metrics are unavailable.")


st.divider()


# 3. RISK-ADJUSTED RETURNS

st.markdown("#### Risk-Adjusted Returns")

ratio_keys = [
    ("sharpe_ratio", "Sharpe Ratio"),
    ("sortino_ratio", "Sortino Ratio")
]

ratio_data = [
    {
        "Indicator": label,
        "Value": indicators[key]["value"]
    }
    for key, label in ratio_keys
    if key in available
    and key in indicators
    and indicators[key].get("value") is not None
]

if ratio_data:

    ratio_df = pd.DataFrame(ratio_data)

    fig = px.bar(
        ratio_df,
        x="Indicator",
        y="Value",
        text="Value",
        color="Indicator",
        title="Risk-Adjusted Performance"
    )

    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside"
    )

    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Ratio",
        margin=dict(t=60, b=30),
        height=350
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:

    st.info("Risk-adjusted return metrics are unavailable.")


st.divider()


# 4. BENCHMARK RISK

st.markdown("#### Benchmark Risk")

if "tracking_error" in available and indicators.get("tracking_error"):

    st.metric(
        "Tracking Error",
        f"{indicators['tracking_error']['value']:.2f}%",
        help="Measures deviation from benchmark returns."
    )

else:

    st.metric("Tracking Error", "N/A")


st.divider()


# --------------------------------------------------
# SECTOR CONCENTRATION
# --------------------------------------------------

st.subheader("Sector Concentration")

concentration = result.get("sector_concentration") or {}
largest_sector = concentration.get("largest_sector") or {}

c1, c2, c3 = st.columns(3)

hhi = concentration.get("hhi")
effective = concentration.get("effective_number_of_sectors")

c1.metric(
    "Herfindahl-Hirschman Index",
    f"{hhi:.3f}" if hhi is not None else "N/A"
)

c2.metric(
    "Effective Number of Sectors",
    f"{effective:.2f}" if effective is not None else "N/A"
)

with c3:
    st.metric(
        "Largest Sector Exposure",
        f"{largest_sector.get('exposure_percentage', 0):.1f}%"
        if largest_sector else "N/A"
    )

    if largest_sector:
        st.caption(largest_sector.get("sector_name", "Unknown sector"))


st.caption(
    f"Total equity exposure: "
    f"{result.get('total_equity_exposure', 0):.2f}%"
)

st.divider()


# --------------------------------------------------
# RISK ALERTS
# --------------------------------------------------

st.subheader("Risk Alerts")

alerts = result.get("risk_alerts", [])

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

    if risk_level == "not_assessed":
        st.info(
            "Risk alerts cannot be assessed because "
            "risk metrics are unavailable."
        )
    else:
        st.success(
            "No risk alerts identified in the available data."
        )


st.divider()


# --------------------------------------------------
# DATA AVAILABILITY AND QUALITY
# --------------------------------------------------

st.subheader("Data Availability & Quality")

if unavailable:

    st.warning(
        "Some risk indicators are unavailable: "
        + ", ".join(unavailable)
    )

else:

    st.success("All nine risk indicators are available.")


quality_alerts = result.get("data_quality_alerts", [])

if quality_alerts:

    for alert in quality_alerts:
        st.warning(alert.get("message", str(alert)))

else:

    st.success("No data quality alerts reported.")


# --------------------------------------------------
# DATA DATES
# --------------------------------------------------

dates = result.get("data_dates", {})

c1, c2 = st.columns(2)

c1.metric(
    "Performance Data Date",
    dates.get("performance_date") or "Unavailable"
)

c2.metric(
    "Risk Calculation Date",
    dates.get("risk_date") or "Unavailable"
)


# --------------------------------------------------
# DISCLAIMERS
# --------------------------------------------------

st.divider()

st.info(
    result.get(
        "thresholds_note",
        "Risk alerts use illustrative thresholds."
    )
)

st.warning(
    result.get(
        "data_note",
        "This is historical analysis, not a live risk assessment."
    )
)

st.caption(
    "PL Capital | Portfolio Analytics Agent | Assessment Project"
)
