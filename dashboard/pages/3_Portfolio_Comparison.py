
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))

from portfolio_comparison import compare_portfolios
from database import get_connection


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Portfolio Comparison | PL Capital",
    page_icon="⚖️",
    layout="wide"
)

st.title("Portfolio Comparison")

st.caption(
    "Compare portfolio performance, risk, asset allocation "
    "and sector concentration."
)


# --------------------------------------------------
# LOAD PORTFOLIOS
# --------------------------------------------------

conn = get_connection()

portfolios = pd.read_sql_query(
    """
    SELECT portfolio_id, portfolio_name, strategy_type,
           target_risk_level, total_aum
    FROM portfolios
    ORDER BY portfolio_name
    """,
    conn
)

conn.close()

if len(portfolios) < 2:
    st.error("At least two portfolios are required for comparison.")
    st.stop()


# --------------------------------------------------
# PORTFOLIO SELECTION
# --------------------------------------------------

st.subheader("Select Portfolios")

portfolio_names = portfolios["portfolio_name"].tolist()

col1, col2 = st.columns(2)

with col1:
    portfolio_1 = st.selectbox(
        "Portfolio A",
        portfolio_names,
        index=portfolio_names.index("Tech Innovation Fund")
        if "Tech Innovation Fund" in portfolio_names else 0
    )

with col2:
    default_index = (
        portfolio_names.index("Growth Equity Fund")
        if "Growth Equity Fund" in portfolio_names
        else 1
    )

    portfolio_2 = st.selectbox(
        "Portfolio B",
        portfolio_names,
        index=default_index
    )


if portfolio_1 == portfolio_2:
    st.warning("Please select two different portfolios.")
    st.stop()


# --------------------------------------------------
# PORTFOLIO OVERVIEW
# --------------------------------------------------

details_1 = portfolios[
    portfolios["portfolio_name"] == portfolio_1
].iloc[0]

details_2 = portfolios[
    portfolios["portfolio_name"] == portfolio_2
].iloc[0]

st.divider()

st.subheader("Portfolio Overview")

overview_1, overview_2 = st.columns(2)

with overview_1:
    st.markdown(f"### {portfolio_1}")
    st.write(f"**Strategy:** {details_1['strategy_type']}")
    st.write(f"**Target Risk:** {details_1['target_risk_level']}")
    st.metric(
        "Assets Under Management",
        f"₹{details_1['total_aum']:,.0f}"
    )

with overview_2:
    st.markdown(f"### {portfolio_2}")
    st.write(f"**Strategy:** {details_2['strategy_type']}")
    st.write(f"**Target Risk:** {details_2['target_risk_level']}")
    st.metric(
        "Assets Under Management",
        f"₹{details_2['total_aum']:,.0f}"
    )


# --------------------------------------------------
# RUN COMPARISON
# --------------------------------------------------

with st.spinner("Comparing portfolios..."):

    result = compare_portfolios(
        portfolio_1,
        portfolio_2
    )

if not result.get("success"):
    st.error(result.get("error", "Comparison failed."))
    st.stop()

metrics = result.get("performance_and_risk", {})


# --------------------------------------------------
# PERFORMANCE AND RISK COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Performance & Risk Comparison")

metric_rows = []

for key, item in metrics.items():

    value_1 = item.get("portfolio_1")
    value_2 = item.get("portfolio_2")
    difference = item.get("difference")

    metric_rows.append({
        "Metric": item["label"],
        portfolio_1: (
            f"{value_1:.2f}{item['unit']}"
            if value_1 is not None else "N/A"
        ),
        portfolio_2: (
            f"{value_2:.2f}{item['unit']}"
            if value_2 is not None else "N/A"
        ),
        "Difference (A - B)": (
            f"{difference:+.2f}{item['unit']}"
            if difference is not None else "N/A"
        ),
        "Availability": (
            "Available"
            if item["availability"] == "available"
            else "Insufficient Data"
        )
    })

comparison_df = pd.DataFrame(metric_rows)

st.dataframe(
    comparison_df,
    width="stretch",
    hide_index=True
)


# --------------------------------------------------
# PERFORMANCE VISUALIZATION
# --------------------------------------------------

st.divider()

st.subheader("Performance Comparison")

return_data = []

for key, label in [
    ("total_return_1y", "1-Year Return"),
    ("volatility", "Volatility")
]:

    item = metrics.get(key, {})

    for portfolio_key, portfolio_name in [
        ("portfolio_1", portfolio_1),
        ("portfolio_2", portfolio_2)
    ]:

        value = item.get(portfolio_key)

        if value is not None:
            return_data.append({
                "Metric": label,
                "Portfolio": portfolio_name,
                "Value": value
            })

if return_data:

    return_df = pd.DataFrame(return_data)

    fig = px.bar(
        return_df,
        x="Metric",
        y="Value",
        color="Portfolio",
        barmode="group",
        text="Value",
        title="Returns and Volatility Comparison"
    )

    fig.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_title="Percentage (%)",
        xaxis_title="",
        height=400
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:
    st.info("Performance comparison data is unavailable.")


# --------------------------------------------------
# RISK METRICS COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Risk Metrics Comparison")

risk_metrics = [
    ("beta", "Beta"),
    ("var_95", "VaR 95%"),
    ("cvar_95", "CVaR 95%"),
    ("tracking_error", "Tracking Error")
]

risk_data = []

for key, label in risk_metrics:

    item = metrics.get(key, {})

    for portfolio_key, portfolio_name in [
        ("portfolio_1", portfolio_1),
        ("portfolio_2", portfolio_2)
    ]:

        value = item.get(portfolio_key)

        if value is not None:
            risk_data.append({
                "Metric": label,
                "Portfolio": portfolio_name,
                "Value": value
            })

if risk_data:

    risk_df = pd.DataFrame(risk_data)

    # Separate charts because Beta and percentages
    # use different units.

    beta_df = risk_df[
        risk_df["Metric"] == "Beta"
    ]

    percentage_df = risk_df[
        risk_df["Metric"] != "Beta"
    ]

    if not beta_df.empty:

        st.markdown("#### Market Sensitivity")

        fig = px.bar(
            beta_df,
            x="Portfolio",
            y="Value",
            color="Portfolio",
            text="Value",
            title="Portfolio Beta"
        )

        fig.update_traces(
            texttemplate="%{text:.2f}",
            textposition="outside"
        )

        fig.update_layout(
            showlegend=False,
            yaxis_title="Beta",
            height=320
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

    if not percentage_df.empty:

        st.markdown("#### Downside and Benchmark Risk")

        fig = px.bar(
            percentage_df,
            x="Metric",
            y="Value",
            color="Portfolio",
            barmode="group",
            text="Value",
            title="Risk Exposure Comparison (%)"
        )

        fig.update_traces(
            texttemplate="%{text:.2f}%",
            textposition="outside"
        )

        fig.update_layout(
            yaxis_title="Percentage (%)",
            height=380
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

else:
    st.info("Risk comparison data is unavailable.")


# --------------------------------------------------
# RISK-ADJUSTED RETURNS
# --------------------------------------------------

st.divider()

st.subheader("Risk-Adjusted Performance")

ratio_data = []

for key, label in [
    ("sharpe_ratio", "Sharpe Ratio"),
    ("sortino_ratio", "Sortino Ratio")
]:

    item = metrics.get(key, {})

    for portfolio_key, portfolio_name in [
        ("portfolio_1", portfolio_1),
        ("portfolio_2", portfolio_2)
    ]:

        value = item.get(portfolio_key)

        if value is not None:
            ratio_data.append({
                "Metric": label,
                "Portfolio": portfolio_name,
                "Value": value
            })

if ratio_data:

    ratio_df = pd.DataFrame(ratio_data)

    fig = px.bar(
        ratio_df,
        x="Metric",
        y="Value",
        color="Portfolio",
        barmode="group",
        text="Value",
        title="Risk-Adjusted Returns"
    )

    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_title="Ratio",
        height=350
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:
    st.info("Risk-adjusted return data is unavailable.")


# --------------------------------------------------
# ASSET ALLOCATION COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Asset Allocation Comparison")

allocation = result.get(
    "asset_allocation_comparison", {}
)

allocation_data = []

for asset_type, values in allocation.items():

    allocation_data.append({
        "Asset Type": asset_type,
        portfolio_1: values["portfolio_1"],
        portfolio_2: values["portfolio_2"]
    })

if allocation_data:

    allocation_df = pd.DataFrame(allocation_data)

    st.dataframe(
        allocation_df,
        width="stretch",
        hide_index=True
    )

    chart_df = allocation_df.melt(
        id_vars="Asset Type",
        var_name="Portfolio",
        value_name="Allocation"
    )

    fig = px.bar(
        chart_df,
        x="Asset Type",
        y="Allocation",
        color="Portfolio",
        barmode="group",
        text="Allocation",
        title="Asset Allocation Distribution"
    )

    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_title="Allocation (%)",
        height=350
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:
    st.info("Asset allocation data is unavailable.")


# --------------------------------------------------
# SECTOR EXPOSURE COMPARISON
# --------------------------------------------------

st.divider()

st.subheader("Sector Exposure Comparison")

sector_comparison = result.get(
    "sector_exposure_comparison", {}
)

sector_data = []

for sector, values in sector_comparison.items():

    sector_data.append({
        "Sector": sector,
        portfolio_1: values["portfolio_1"],
        portfolio_2: values["portfolio_2"]
    })

if sector_data:

    sector_df = pd.DataFrame(sector_data)

    st.dataframe(
        sector_df,
        width="stretch",
        hide_index=True
    )

    sector_chart_df = sector_df.melt(
        id_vars="Sector",
        var_name="Portfolio",
        value_name="Exposure"
    )

    fig = px.bar(
        sector_chart_df,
        x="Sector",
        y="Exposure",
        color="Portfolio",
        barmode="group",
        text="Exposure",
        title="Sector Exposure Distribution"
    )

    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="Sector",
        yaxis_title="Equity Exposure (%)",
        height=420
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

else:
    st.info("Sector exposure data is unavailable.")


# --------------------------------------------------
# SECTOR CONCENTRATION
# --------------------------------------------------

st.divider()

st.subheader("Sector Concentration Comparison")

concentration = result.get(
    "concentration_comparison", {}
)

hhi = concentration.get("hhi", {})
effective = concentration.get(
    "effective_number_of_sectors", {}
)

c1, c2 = st.columns(2)

with c1:
    st.markdown(f"**{portfolio_1}**")

    st.metric(
        "HHI",
        f"{hhi.get('portfolio_1'):.3f}"
        if hhi.get("portfolio_1") is not None else "N/A"
    )

    st.metric(
        "Effective Sectors",
        f"{effective.get('portfolio_1'):.2f}"
        if effective.get("portfolio_1") is not None else "N/A"
    )

with c2:
    st.markdown(f"**{portfolio_2}**")

    st.metric(
        "HHI",
        f"{hhi.get('portfolio_2'):.3f}"
        if hhi.get("portfolio_2") is not None else "N/A"
    )

    st.metric(
        "Effective Sectors",
        f"{effective.get('portfolio_2'):.2f}"
        if effective.get("portfolio_2") is not None else "N/A"
    )


# --------------------------------------------------
# DATA QUALITY
# --------------------------------------------------

st.divider()

st.subheader("Data Availability & Quality")

quality = result.get("data_quality", {})

quality_col1, quality_col2 = st.columns(2)

for column, portfolio_key, portfolio_name in [
    (quality_col1, "portfolio_1", portfolio_1),
    (quality_col2, "portfolio_2", portfolio_2)
]:

    data = quality.get(portfolio_key, {})

    with column:

        st.markdown(f"**{portfolio_name}**")

        st.write(
            "Analysis Status:",
            str(data.get("analysis_status", "Unknown")).replace(
                "_", " "
            ).title()
        )

        st.write(
            "Unallocated Total Portfolio Allocation:",
            f"{data.get('unallocated_allocation', 0):.2f}%"
            if data.get("unallocated_allocation") is not None
            else "N/A"
        )

        st.write(
            "Missing Sector Exposure:",
            f"{data.get('missing_sector_exposure', 0):.2f}%"
            if data.get("missing_sector_exposure") is not None
            else "N/A"
        )


# --------------------------------------------------
# DATA DATES
# --------------------------------------------------

st.divider()

st.subheader("Underlying Data Dates")

dates = result.get("data_dates", {})

date_col1, date_col2 = st.columns(2)

with date_col1:

    st.markdown(f"**{portfolio_1}**")

    st.write(
        "Performance Date:",
        dates.get("portfolio_1_performance_date") or "Unavailable"
    )

    st.write(
        "Risk Date:",
        dates.get("portfolio_1_risk_date") or "Unavailable"
    )

with date_col2:

    st.markdown(f"**{portfolio_2}**")

    st.write(
        "Performance Date:",
        dates.get("portfolio_2_performance_date") or "Unavailable"
    )

    st.write(
        "Risk Date:",
        dates.get("portfolio_2_risk_date") or "Unavailable"
    )


# --------------------------------------------------
# DISCLAIMER
# --------------------------------------------------

st.divider()

st.info(
    result.get(
        "data_note",
        "Comparison uses the latest available historical records."
    )
)

st.caption(
    "PL Capital | Portfolio Analytics Agent | Assessment Project"
)
