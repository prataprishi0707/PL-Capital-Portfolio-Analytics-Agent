
import os
import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "portfolio_database.db")

st.set_page_config(
    page_title="PL Capital | Portfolio Intelligence",
    page_icon="📊",
    layout="wide"
)

st.title("PL Capital | Portfolio Intelligence")
st.caption("Portfolio Analytics & Risk Intelligence Dashboard")

if not os.path.exists(DB_PATH):
    st.error(f"Database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)

    portfolios = pd.read_sql_query(
        "SELECT * FROM portfolios", conn
    )

    holdings = pd.read_sql_query("""
        SELECT
            h.portfolio_id,
            h.current_weight,
            s.asset_type,
            sec.sector_name
        FROM holdings h
        JOIN securities s
            ON h.security_id = s.security_id
        LEFT JOIN sectors sec
            ON s.sector_id = sec.sector_id
    """, conn)

    conn.close()
    return portfolios, holdings


portfolios, holdings = load_data()

# Sidebar filters
st.sidebar.header("Dashboard Filters")

portfolio_options = (
    ["All Portfolios"] + portfolios["portfolio_name"].tolist()
)

selected_portfolio = st.sidebar.selectbox(
    "Select Portfolio",
    portfolio_options
)

if selected_portfolio != "All Portfolios":

    filtered_portfolios = portfolios[
        portfolios["portfolio_name"] == selected_portfolio
    ]

    filtered_ids = filtered_portfolios["portfolio_id"].tolist()

    filtered_holdings = holdings[
        holdings["portfolio_id"].isin(filtered_ids)
    ]

else:
    filtered_portfolios = portfolios
    filtered_holdings = holdings


# KPI calculations
total_portfolios = len(filtered_portfolios)

filtered_portfolios = filtered_portfolios.copy()

filtered_portfolios["total_aum"] = pd.to_numeric(
    filtered_portfolios["total_aum"],
    errors="coerce"
).fillna(0)

total_aum = filtered_portfolios["total_aum"].sum()

# Merge portfolio AUM with holdings
allocation_data = filtered_holdings.merge(
    filtered_portfolios[["portfolio_id", "total_aum"]],
    on="portfolio_id",
    how="left"
)

allocation_data["current_weight"] = pd.to_numeric(
    allocation_data["current_weight"],
    errors="coerce"
).fillna(0)

allocation_data["weighted_exposure"] = (
    allocation_data["current_weight"] *
    allocation_data["total_aum"]
)

total_filtered_aum = total_aum

if total_filtered_aum > 0:

    equity_exposure = allocation_data[
        allocation_data["asset_type"].str.lower() == "stock"
    ]["weighted_exposure"].sum()

    bond_exposure = allocation_data[
        allocation_data["asset_type"].str.lower() == "bond"
    ]["weighted_exposure"].sum()

    equity_weight = equity_exposure / total_filtered_aum * 100

    bond_weight = bond_exposure / total_filtered_aum * 100

else:
    equity_weight = 0
    bond_weight = 0

unallocated_weight = 100 - equity_weight - bond_weight


# KPI cards
c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Portfolios", total_portfolios)
c2.metric("Total AUM", f"₹{total_aum:,.0f}")
c3.metric("Equity Allocation", f"{equity_weight:.1f}%")
c4.metric("Bond Allocation", f"{bond_weight:.1f}%")


st.divider()


# Charts
left, right = st.columns(2)

with left:

    st.subheader("Portfolio-wise AUM")

    aum_chart = filtered_portfolios.copy()

    fig = px.bar(
        aum_chart,
        x="portfolio_name",
        y="total_aum",
        color="strategy_type",
        title="Assets Under Management"
    )

    fig.update_layout(
        xaxis_title="Portfolio",
        yaxis_title="AUM",
        xaxis_tickangle=-35
    )

    st.plotly_chart(fig, width="stretch")


with right:

    st.subheader("Asset Allocation")

    if unallocated_weight < -0.1:
        st.warning(
            f"Asset allocation exceeds total AUM by "
            f"{abs(unallocated_weight):.2f} percentage points."
        )

    # Avoid negative pie-chart slices
    if unallocated_weight >= 0:

        allocation = pd.DataFrame({
            "Asset Type": ["Equity", "Bonds", "Unallocated"],
            "Weight (%)": [
                equity_weight,
                bond_weight,
                unallocated_weight
            ]
        })

    else:

        allocation = pd.DataFrame({
            "Asset Type": ["Equity", "Bonds"],
            "Weight (%)": [
                equity_weight,
                bond_weight
            ]
        })

    fig = px.pie(
        allocation,
        names="Asset Type",
        values="Weight (%)",
        hole=0.45,
        title="Equity vs Bond Allocation"
    )

    st.plotly_chart(fig, width="stretch")


# Portfolio Directory
st.divider()
st.subheader("Portfolio Directory")

display_columns = [
    "portfolio_name",
    "strategy_type",
    "target_risk_level",
    "total_aum",
    "status"
]

st.dataframe(
    filtered_portfolios[display_columns],
    width="stretch",
    hide_index=True
)


# Data transparency
st.divider()

st.warning(
    "Data note: This dashboard uses the supplied historical assessment "
    "dataset. It is not connected to live market prices or live portfolio feeds."
)

st.caption(
    "PL Capital | Portfolio Analytics Agent | Assessment Project"
)
