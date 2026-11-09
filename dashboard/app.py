"""
PL Capital — Executive Overview
Entry point for the Streamlit multi-page application.
All data sourced directly from portfolio_database.db via read-only SQL.
No financial calculations are duplicated here; summary metrics are aggregated
directly from stored database values.
"""

import sys, os
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from database import get_connection
from portfolio_health import analyze_portfolio_health

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PL Capital | Portfolio Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pl_theme import (
    inject_css, page_header, sidebar_logo, sidebar_nav_section,
    disclaimer, data_note, fmt_aum, GOLD, NAVY, RED, AMBER, GREEN,
    MID_GREY, WHITE, CHART_COLORS, LIGHT_GREY,
)
inject_css()

# ── Sidebar ───────────────────────────────────────────────────────────────────
sidebar_logo()
st.sidebar.markdown("Navigate to a section using the pages listed in the sidebar.")
st.sidebar.markdown("---")
sidebar_nav_section("PAGES")
st.sidebar.page_link("app.py",                              label="📊 Executive Overview",    icon=None)
st.sidebar.page_link("pages/1_Portfolio_Explorer.py",       label="🔎 Portfolio Explorer",     icon=None)
st.sidebar.page_link("pages/2_Risk_Intelligence.py",        label="🛡️ Risk Intelligence",      icon=None)
st.sidebar.page_link("pages/3_Portfolio_Comparison.py",     label="⚖️ Portfolio Comparison",   icon=None)
st.sidebar.page_link("pages/4_AI_Analyst.py",               label="🤖 AI Analyst",             icon=None)
st.sidebar.page_link("pages/5_Reconciliation.py",           label="🔍 Reconciliation",         icon=None)

DB_PATH = PROJECT_DIR / "portfolio_database.db"
if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()

# ── Load core data (read-only SQL) ────────────────────────────────────────────
@st.cache_data(ttl=120)
def load_overview_data():
    conn = get_connection()
    portfolios = pd.read_sql_query("SELECT * FROM portfolios ORDER BY portfolio_id", conn)
    holdings = pd.read_sql_query("""
        SELECT h.portfolio_id, h.current_weight,
               s.asset_type, sec.sector_name
        FROM holdings h
        JOIN securities s ON h.security_id = s.security_id
        LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
    """, conn)
    risk_metrics = pd.read_sql_query("""
        SELECT rm.portfolio_id, rm.beta, rm.var_95, rm.calculation_date
        FROM risk_metrics rm
        INNER JOIN (
            SELECT portfolio_id, MAX(calculation_date) AS max_date
            FROM risk_metrics GROUP BY portfolio_id
        ) latest ON rm.portfolio_id=latest.portfolio_id
                  AND rm.calculation_date=latest.max_date
    """, conn)
    conn.close()
    return portfolios, holdings, risk_metrics

portfolios, holdings, risk_metrics = load_overview_data()

# ── Page header ────────────────────────────────────────────────────────────────
page_header("📊", "Executive Overview",
            "Portfolio intelligence summary · PL Capital Analytics Platform")

# ── KPI row ────────────────────────────────────────────────────────────────────
total_aum = portfolios["total_aum"].sum()
active_n  = (portfolios["status"].str.lower() == "active").sum()
passive_n = (portfolios["status"].str.lower() == "passive").sum()

# Beta Alerts: portfolios with latest Beta > 1.2 in stored risk_metrics.
# This is a single-threshold indicator, not the complete risk engine assessment.
high_beta = risk_metrics[risk_metrics["beta"].notna() & (risk_metrics["beta"] > 1.2)]
beta_alert_count = len(high_beta)

# Quickly compute health scores for all portfolios (cached)
@st.cache_data(ttl=120)
def load_health_scores():
    scores = []
    conn = get_connection()
    names = pd.read_sql_query("SELECT portfolio_name FROM portfolios", conn)["portfolio_name"].tolist()
    conn.close()
    for n in names:
        r = analyze_portfolio_health(n)
        if r.get("success"):
            scores.append({
                "portfolio_name": n,
                "health_score": r.get("health_score"),
                "health_tier": r.get("health_tier", ""),
                "risk_level": r.get("alerts"),
            })
    return scores

with st.spinner("Computing portfolio health scores…"):
    health_scores = load_health_scores()

health_df = pd.DataFrame(health_scores)
avg_health = health_df["health_score"].mean() if not health_df.empty else None

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Portfolios", len(portfolios))
k2.metric("Total AUM", fmt_aum(total_aum))
k3.metric("Active / Passive", f"{active_n} / {passive_n}")
k4.metric("Avg Health Score",
          f"{avg_health:.0f} / 100" if avg_health is not None else "N/A",
          help="Mean health score across all portfolios. Lower = needs attention.")
k5.metric("Beta Alerts",
          str(beta_alert_count),
          delta=None,
          help="Portfolios with latest stored Beta > 1.2 (single-threshold indicator). "
               "This is not the complete risk engine assessment — see Risk Intelligence for full analysis.")

disclaimer(
    "Health Score is a heuristic aggregate (100 = no detected issues). "
    "Beta Alerts count portfolios with latest stored Beta > 1.2 — this is a single-threshold "
    "indicator from the risk_metrics table, not the complete risk engine assessment. "
    "All values are sourced from the historical dataset, not live market data."
)

st.markdown("---")

# ── Charts row ────────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("#### AUM Distribution by Portfolio")
    aum_df = portfolios[["portfolio_name", "total_aum", "strategy_type"]].copy()
    aum_df["aum_m"] = aum_df["total_aum"] / 1_000_000
    aum_df = aum_df.sort_values("aum_m", ascending=True)
    fig_aum = px.bar(
        aum_df, x="aum_m", y="portfolio_name", orientation="h",
        color="strategy_type",
        color_discrete_sequence=CHART_COLORS,
        labels={"aum_m": "AUM (₹M)", "portfolio_name": "", "strategy_type": "Strategy"},
        text=aum_df["aum_m"].apply(lambda x: f"₹{x:.0f}M"),
    )
    fig_aum.update_traces(textposition="outside")
    fig_aum.update_layout(
        height=420, showlegend=True,
        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        font=dict(family="sans-serif", color=NAVY),
        margin=dict(l=10, r=50, t=10, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        xaxis=dict(showgrid=True, gridcolor="#E8EDF2"),
    )
    st.plotly_chart(fig_aum, use_container_width=True)

with col_r:
    st.markdown("#### Health Score Distribution")
    if not health_df.empty and health_df["health_tier"].notna().any():
        tier_counts = health_df["health_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        tier_order = ["healthy", "moderate", "attention_needed"]
        tier_labels = {"healthy": "Healthy (≥80)", "moderate": "Moderate (55–79)",
                       "attention_needed": "Needs Attention (<55)"}
        tier_colors_map = {"healthy": GREEN, "moderate": AMBER, "attention_needed": RED}
        tier_counts["label"] = tier_counts["tier"].map(tier_labels)
        tier_counts["color"] = tier_counts["tier"].map(tier_colors_map)
        fig_health = px.pie(
            tier_counts, values="count", names="label",
            color="tier",
            color_discrete_map={
                "Healthy (≥80)": GREEN, "Moderate (55–79)": AMBER,
                "Needs Attention (<55)": RED,
            },
            hole=0.52,
        )
        fig_health.update_traces(
            textinfo="percent+label",
            marker=dict(colors=[tier_colors_map.get(t, MID_GREY) for t in tier_counts["tier"]])
        )
        fig_health.update_layout(
            height=420, showlegend=True,
            plot_bgcolor=WHITE, paper_bgcolor=WHITE,
            font=dict(family="sans-serif", color=NAVY),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_health, use_container_width=True)
    else:
        st.info("Health scores unavailable.")

st.markdown("---")

# ── Risk overview ──────────────────────────────────────────────────────────────
st.markdown("#### Risk Overview — Latest Metrics")

if not risk_metrics.empty:
    risk_merged = risk_metrics.merge(
        portfolios[["portfolio_id", "portfolio_name", "target_risk_level"]],
        on="portfolio_id", how="left"
    )
    risk_display = risk_merged[["portfolio_name", "target_risk_level", "beta", "var_95", "calculation_date"]].copy()
    risk_display.columns = ["Portfolio", "Target Risk", "Beta", "VaR 95%", "Data Date"]
    risk_display["Beta"] = risk_display["Beta"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    risk_display["VaR 95%"] = risk_display["VaR 95%"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
    st.dataframe(risk_display, use_container_width=True, hide_index=True, height=280)
else:
    st.info("No risk metrics available.")

st.markdown("---")

# ── Portfolio monitoring table ─────────────────────────────────────────────────
st.markdown("#### Portfolio Monitoring Summary")

mon = portfolios[["portfolio_name", "strategy_type", "target_risk_level", "total_aum", "status"]].copy()
mon["total_aum"] = mon["total_aum"].apply(fmt_aum)
if not health_df.empty:
    mon = mon.merge(
        health_df[["portfolio_name", "health_score", "health_tier"]],
        on="portfolio_name", how="left"
    )
    mon["health_score"] = mon["health_score"].apply(
        lambda x: f"{int(x)}/100" if pd.notna(x) else "N/A"
    )
    mon["health_tier"] = mon["health_tier"].str.replace("_", " ").str.title()
mon.columns = [c.replace("_", " ").title() for c in mon.columns]
st.dataframe(mon, use_container_width=True, hide_index=True)

st.markdown("---")

# ── AUM by strategy and risk level ────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.markdown("#### AUM by Strategy Type")
    by_strategy = portfolios.groupby("strategy_type")["total_aum"].sum().reset_index()
    by_strategy.columns = ["Strategy", "AUM"]
    by_strategy["AUM_M"] = by_strategy["AUM"] / 1_000_000
    fig_s = px.bar(by_strategy.sort_values("AUM_M", ascending=False),
                   x="Strategy", y="AUM_M", color="Strategy",
                   color_discrete_sequence=CHART_COLORS,
                   labels={"AUM_M": "AUM (₹M)", "Strategy": ""})
    fig_s.update_layout(showlegend=False, height=300,
                        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                        font=dict(color=NAVY),
                        margin=dict(l=5, r=5, t=10, b=40))
    st.plotly_chart(fig_s, use_container_width=True)

with c2:
    st.markdown("#### Portfolio Count by Target Risk")
    by_risk = portfolios["target_risk_level"].value_counts().reset_index()
    by_risk.columns = ["Risk Level", "Count"]
    fig_r = px.pie(by_risk, values="Count", names="Risk Level",
                   color="Risk Level",
                   color_discrete_map={"High": RED, "Medium": AMBER, "Low": GREEN},
                   hole=0.48)
    fig_r.update_layout(height=300, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                        font=dict(color=NAVY), margin=dict(l=5, r=5, t=10, b=10))
    st.plotly_chart(fig_r, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
data_note(
    "All data sourced from portfolio_database.db (historical assessment dataset). "
    "Not connected to live market prices, live portfolio feeds or investment advisory systems."
)
st.caption("PL Capital · Portfolio Analytics Agent · Assessment Project")
