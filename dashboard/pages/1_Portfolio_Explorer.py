"""
PL Capital — Portfolio Explorer
Deep-dive into a single portfolio: holdings, allocation, sector exposure,
performance and alerts. All data from the database and existing backend functions.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pl_theme import (
    inject_css, page_header, sidebar_logo, sidebar_nav_section,
    disclaimer, data_note, fmt_aum, badge, metric_na,
    GOLD, NAVY, RED, AMBER, GREEN, MID_GREY, WHITE, CHART_COLORS,
    health_color,
)
inject_css()

from portfolio_health import analyze_portfolio_health
from database import get_connection

st.set_page_config(
    page_title="Portfolio Explorer | PL Capital",
    page_icon="🔎",
    layout="wide",
)

sidebar_logo()
sidebar_nav_section("NAVIGATION")
st.sidebar.page_link("app.py",                              label="📊 Executive Overview")
st.sidebar.page_link("pages/1_Portfolio_Explorer.py",       label="🔎 Portfolio Explorer")
st.sidebar.page_link("pages/2_Risk_Intelligence.py",        label="🛡️ Risk Intelligence")
st.sidebar.page_link("pages/3_Portfolio_Comparison.py",     label="⚖️ Portfolio Comparison")
st.sidebar.page_link("pages/4_AI_Analyst.py",               label="🤖 AI Analyst")
st.sidebar.page_link("pages/5_Reconciliation.py",           label="🔍 Reconciliation")

page_header("🔎", "Portfolio Explorer",
            "Holdings composition · Sector exposure · Performance indicators")

# ── Portfolio selector ────────────────────────────────────────────────────────
conn = get_connection()
portfolios = pd.read_sql_query(
    "SELECT portfolio_id, portfolio_name, strategy_type, target_risk_level, total_aum, status "
    "FROM portfolios ORDER BY portfolio_name", conn)
conn.close()

sel_col, meta_col = st.columns([2, 3])
with sel_col:
    selected = st.selectbox("Select Portfolio", portfolios["portfolio_name"].tolist(),
                            label_visibility="collapsed",
                            key="explorer_selector")
    st.caption("Select a portfolio to explore")

meta_row = portfolios[portfolios["portfolio_name"] == selected].iloc[0]
with meta_col:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("AUM", fmt_aum(meta_row["total_aum"]))
    m2.metric("Strategy", meta_row["strategy_type"])
    m3.metric("Target Risk", meta_row["target_risk_level"])
    m4.metric("Status", meta_row["status"])

st.markdown("---")

# ── Backend call ──────────────────────────────────────────────────────────────
with st.spinner("Analysing portfolio…"):
    result = analyze_portfolio_health(selected)

if not result.get("success"):
    st.error(f"Analysis failed: {result.get('error')}")
    st.stop()

portfolio = result["portfolio"]
performance = result.get("performance") or {}
risk = result.get("risk_metrics") or {}
health_score = result.get("health_score")
health_tier = result.get("health_tier", "")
analysis_status = result.get("analysis_status", "")

# ── Health score banner ────────────────────────────────────────────────────────
tier_icons = {"healthy": "✅", "moderate": "⚠️", "attention_needed": "❌"}
tier_labels = {"healthy": "Healthy", "moderate": "Moderate", "attention_needed": "Needs Attention"}
tier_icon = tier_icons.get(health_tier, "ℹ️")

h_color = health_color(health_tier)
h_pct = health_score if health_score is not None else 0
st.markdown(
    f"""<div style="background:{WHITE};border-radius:8px;padding:1rem 1.5rem;
        border-left:5px solid {h_color};display:flex;align-items:center;
        gap:1.5rem;box-shadow:0 1px 4px rgba(10,22,40,0.07);">
        <div style="font-size:2rem;">{tier_icon}</div>
        <div style="flex:1">
            <div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:.08em;
                color:{MID_GREY};font-weight:700;">Portfolio Health</div>
            <div style="font-size:1.4rem;font-weight:800;color:{h_color};">
                {health_score}/100 — {tier_labels.get(health_tier,'—')}
            </div>
            <div style="font-size:0.78rem;color:{MID_GREY};">
                Analysis status: <b>{analysis_status.replace('_',' ').title()}</b>
                &nbsp;·&nbsp; Benchmark: {portfolio.get('benchmark_index','N/A')}
            </div>
        </div>
        <div style="width:160px;">
            <div style="background:#E8EDF2;border-radius:4px;height:10px;">
                <div style="background:{h_color};width:{h_pct}%;height:10px;border-radius:4px;"></div>
            </div>
            <div style="text-align:right;font-size:0.7rem;color:{MID_GREY};margin-top:3px;">
                Score formula: start 100, deduct for alerts, HHI, missing data
            </div>
        </div>
    </div>""",
    unsafe_allow_html=True
)
st.markdown("")

# ── Risk alerts ───────────────────────────────────────────────────────────────
alerts = result.get("alerts", [])
dq_alerts = result.get("data_quality_alerts", [])

if alerts or dq_alerts:
    with st.expander(f"⚠️ {len(alerts)} risk alert(s) · {len(dq_alerts)} data-quality note(s)", expanded=len(alerts) > 0):
        for a in alerts:
            sev = a.get("severity", "medium")
            if sev == "high":
                st.error(f"🔴 {a['message']}")
            else:
                st.warning(f"🟠 {a['message']}")
        for a in dq_alerts:
            st.info(f"ℹ️ {a.get('message', str(a))}")
else:
    st.success("✅ No risk alerts or data quality issues detected.")

st.markdown("---")

# ── Asset allocation + sector exposure ────────────────────────────────────────
tab_alloc, tab_sector, tab_holdings, tab_perf = st.tabs(
    ["💼 Asset Allocation", "🏭 Sector Exposure", "📋 Holdings", "📈 Performance & Risk"]
)

with tab_alloc:
    asset_data = result.get("asset_allocation", [])
    if asset_data:
        alloc_df = pd.DataFrame(asset_data)
        a_left, a_right = st.columns([1, 1])
        with a_left:
            fig_a = px.pie(
                alloc_df, names="asset_type", values="allocation_percentage",
                hole=0.52, color="asset_type",
                color_discrete_map={"Stock": GOLD, "Bond": "#4E79A7"},
            )
            fig_a.update_traces(textinfo="percent+label")
            fig_a.update_layout(
                height=320, showlegend=True,
                plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                font=dict(color=NAVY), margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(fig_a, use_container_width=True)
        with a_right:
            st.markdown("##### Allocation Detail")
            display_a = alloc_df.copy()
            display_a.columns = ["Asset Type", "Holdings", "Allocation (%)"]
            st.dataframe(display_a, use_container_width=True, hide_index=True)

            unalloc = result.get("unallocated_allocation", 0)
            if abs(unalloc) > 0.01:
                st.warning(f"Unallocated: {unalloc:.2f}%")
            else:
                st.success("Allocation sums to 100%")
    else:
        st.info("No asset allocation data available.")

with tab_sector:
    sector_data = result.get("sector_exposures", [])
    concentration = result.get("sector_concentration", {}) or {}
    if sector_data:
        sector_df = pd.DataFrame(sector_data)
        s_left, s_right = st.columns([2, 1])
        with s_left:
            fig_s = px.bar(
                sector_df.sort_values("exposure_percentage", ascending=True),
                x="exposure_percentage", y="sector_name",
                orientation="h",
                color="exposure_percentage",
                color_continuous_scale=[[0, "#4E79A7"], [1, GOLD]],
                labels={"exposure_percentage": "Equity Exposure (%)", "sector_name": ""},
                text=sector_df["exposure_percentage"].apply(lambda x: f"{x:.1f}%"),
            )
            fig_s.update_traces(textposition="outside")
            fig_s.update_coloraxes(showscale=False)
            fig_s.update_layout(
                height=max(280, len(sector_df) * 42),
                plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                font=dict(color=NAVY), margin=dict(l=10, r=50, t=10, b=30),
            )
            st.plotly_chart(fig_s, use_container_width=True)
        with s_right:
            st.markdown("##### Concentration")
            hhi = concentration.get("hhi")
            eff = concentration.get("effective_number_of_sectors")
            largest = concentration.get("largest_sector") or {}
            st.metric("HHI", f"{hhi:.3f}" if hhi else "N/A",
                      help="Herfindahl-Hirschman Index. Closer to 1 = more concentrated.")
            st.metric("Effective Sectors", f"{eff:.2f}" if eff else "N/A")
            st.metric("Largest Sector",
                      largest.get("sector_name", "N/A"),
                      f"{largest.get('exposure_percentage', 0):.1f}% of equity")
            missing_sec = result.get("missing_sector_exposure", 0)
            if missing_sec > 0.01:
                st.warning(f"{missing_sec:.2f}% exposure has no sector mapping")
    else:
        st.info("No equity sector exposure data (portfolio may be bonds-only).")

with tab_holdings:
    conn = get_connection()
    h_df = pd.read_sql_query("""
        SELECT s.symbol, s.company_name, s.asset_type,
               sec.sector_name, h.quantity,
               h.cost_basis, s.current_price,
               ROUND(h.current_weight * 100, 2) AS weight_pct
        FROM holdings h
        JOIN securities s ON h.security_id = s.security_id
        LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
        JOIN portfolios p ON h.portfolio_id = p.portfolio_id
        WHERE LOWER(p.portfolio_name) = LOWER(?)
        ORDER BY h.current_weight DESC
    """, conn, params=(selected,))
    conn.close()
    if not h_df.empty:
        h_df["market_value"] = (h_df["quantity"] * h_df["current_price"]).round(2)
        h_df["sector_name"] = h_df["sector_name"].fillna("—")
        display_h = h_df[["symbol","company_name","asset_type","sector_name",
                           "quantity","cost_basis","current_price","weight_pct","market_value"]].copy()
        display_h.columns = ["Symbol","Company","Type","Sector",
                              "Qty","Cost Basis","Price","Weight %","Mkt Value"]
        st.dataframe(display_h, use_container_width=True, hide_index=True)
        data_note("current_price from securities table (historical dataset, not live market price).")
    else:
        st.info("No holdings data available.")

with tab_perf:
    p_col, r_col = st.columns(2)
    with p_col:
        st.markdown("##### Performance Metrics")
        if performance:
            def _perf(key, suffix="%"):
                v = performance.get(key)
                return f"{v:.2f}{suffix}" if v is not None else "N/A"

            st.metric("1-Month Return",  _perf("total_return_1m"))
            st.metric("3-Month Return",  _perf("total_return_3m"))
            st.metric("1-Year Return",   _perf("total_return_1y"))
            st.metric("Sharpe Ratio",    _perf("sharpe_ratio", ""))
            st.metric("Max Drawdown",    _perf("max_drawdown"))
            st.metric("Volatility",      _perf("volatility"))
            st.caption(f"Performance date: {performance.get('performance_date', 'N/A')}")
        else:
            st.info("Performance data not available for this portfolio.")
            st.markdown(
                f'<div style="background:#EFF4FA;border-radius:6px;padding:0.8rem 1rem;'
                f'border-left:4px solid {MID_GREY};font-size:0.82rem;color:{MID_GREY};">'
                f'Performance and risk records are only available for a subset of portfolios '
                f'in the supplied dataset. This portfolio has holdings data only.</div>',
                unsafe_allow_html=True
            )
    with r_col:
        st.markdown("##### Risk Metrics")
        if risk:
            def _risk(key, suffix=""):
                v = risk.get(key)
                return f"{v:.2f}{suffix}" if v is not None else "N/A"

            st.metric("Beta",             _risk("beta"),
                      help="Market sensitivity. >1.2 triggers alert threshold.")
            st.metric("VaR 95%",          _risk("var_95", "%"),
                      help="95% Value at Risk.")
            st.metric("VaR 99%",          _risk("var_99", "%"))
            st.metric("CVaR 95%",         _risk("cvar_95", "%"))
            st.metric("Sortino Ratio",    _risk("sortino_ratio"))
            st.metric("Tracking Error",   _risk("tracking_error", "%"))
            st.caption(f"Risk calculation date: {risk.get('calculation_date', 'N/A')}")
        else:
            st.info("Risk metrics not available for this portfolio.")

st.markdown("---")
data_note(
    "All values sourced from portfolio_database.db. "
    "Performance and risk figures are historical dataset records, not live market data. "
    f"Health Score formula: {result.get('health_score_note','see documentation')}."
)
st.caption("PL Capital · Portfolio Analytics Agent")
