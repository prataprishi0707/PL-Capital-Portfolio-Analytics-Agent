"""
PL Capital — Risk Intelligence
Presents risk signals, scores, metric detail and data-completeness context.
Never visually implies that a high score guarantees safety.
All data from the database via existing backend functions.
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
    disclaimer, data_note, badge, metric_na,
    GOLD, NAVY, RED, AMBER, GREEN, MID_GREY, WHITE, CHART_COLORS,
    tier_color, risk_level_badge_html,
)
inject_css()

from risk_analyzer import analyze_portfolio_risk
from database import get_connection

st.set_page_config(
    page_title="Risk Intelligence | PL Capital",
    page_icon="🛡️",
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

page_header("🛡️", "Risk Intelligence",
            "Market sensitivity · Downside risk · Assessment confidence")

# ── Portfolio selector ────────────────────────────────────────────────────────
conn = get_connection()
portfolios = pd.read_sql_query(
    "SELECT portfolio_name FROM portfolios ORDER BY portfolio_name", conn)
conn.close()

if portfolios.empty:
    st.error("No portfolios found.")
    st.stop()

selected = st.selectbox("Select Portfolio", portfolios["portfolio_name"].tolist(),
                        label_visibility="collapsed")
st.caption("Select a portfolio to view risk analysis")
st.markdown("---")

with st.spinner("Running risk analysis…"):
    result = analyze_portfolio_risk(selected)

if not result.get("success"):
    st.error(f"Risk analysis failed: {result.get('error')}")
    st.stop()

risk_level       = result.get("risk_level", "not_assessed")
risk_score       = result.get("risk_score")
risk_tier        = result.get("risk_tier", "not_assessed")
score_tier_unc   = result.get("score_tier_uncapped", "")
completeness     = result.get("data_completeness_pct", 0)
confidence       = result.get("assessment_confidence", "low")
available        = result.get("available_metrics", [])
unavailable      = result.get("unavailable_metrics", [])
indicators       = result.get("risk_indicators") or {}
alerts           = result.get("risk_alerts", [])
analysis_status  = result.get("analysis_status", "")
consistency_note = result.get("consistency_note", "")

# ── Risk classification banner ────────────────────────────────────────────────
tier_c = tier_color(risk_tier)
level_icon = {"high": "🔴", "moderate": "🟠",
              "lower_observed_signals": "🟢", "not_assessed": "⚪"}.get(risk_level, "⚪")
level_label = {"high": "High Risk Signal", "moderate": "Moderate Signal",
               "lower_observed_signals": "Lower Observed Signals",
               "not_assessed": "Not Assessed"}.get(risk_level, risk_level.upper())
confidence_icon = {"high": "●●●", "medium": "●●○", "low": "●○○"}.get(confidence, "○○○")
confidence_color = {"high": GREEN, "medium": AMBER, "low": RED}.get(confidence, MID_GREY)

score_display = f"{risk_score}/100" if risk_score is not None else "N/A"
score_note = "Lower score = more detected risk factors." if risk_score is not None else ""

st.markdown(
    f"""<div style="background:{WHITE};border-radius:10px;padding:1.2rem 1.6rem;
        box-shadow:0 1px 6px rgba(10,22,40,0.09);margin-bottom:1rem;
        display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:1rem;
        border-top:4px solid {tier_c};">
        <div>
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.08em;
                color:{MID_GREY};font-weight:700;">Risk Signal (Authoritative Headline)</div>
            <div style="font-size:1.5rem;font-weight:800;color:{tier_c};">
                {level_icon} {level_label}</div>
            <div style="font-size:0.78rem;color:{MID_GREY};margin-top:4px;">
                Derived from active risk alerts — cannot be overridden by the score.</div>
        </div>
        <div>
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.08em;
                color:{MID_GREY};font-weight:700;">Risk Score</div>
            <div style="font-size:1.4rem;font-weight:700;color:{tier_c};">{score_display}</div>
            <div style="font-size:0.72rem;color:{MID_GREY};">{score_note}</div>
        </div>
        <div>
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.08em;
                color:{MID_GREY};font-weight:700;">Risk Tier (Signal-Capped)</div>
            <div style="font-size:1.4rem;font-weight:700;color:{tier_c};">
                {risk_tier.replace('_',' ').title()}</div>
            <div style="font-size:0.72rem;color:{MID_GREY};">
                Uncapped: {score_tier_unc.replace('_',' ').title()}</div>
        </div>
        <div>
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.08em;
                color:{MID_GREY};font-weight:700;">Assessment Confidence</div>
            <div style="font-size:1.3rem;font-weight:700;color:{confidence_color};">
                {confidence_icon}</div>
            <div style="font-size:0.8rem;color:{MID_GREY};">
                {completeness:.0f}% of {result.get('total_indicators',9)} indicators present</div>
        </div>
    </div>""",
    unsafe_allow_html=True
)

# Capping explanation when signal differs from uncapped tier
if risk_tier != score_tier_unc and risk_score is not None:
    st.markdown(
        f"""<div style="background:#FDECEA;border-left:4px solid {RED};
            border-radius:6px;padding:0.65rem 1rem;font-size:0.82rem;color:#5C1313;
            margin-bottom:0.8rem;">
            ⚠️ <b>Score-tier override:</b> The numeric score ({risk_score}/100) would suggest 
            <em>{score_tier_unc}</em>, but the authoritative risk signal is <b>{risk_level.replace('_',' ')}</b>, 
            so the reported tier is capped at <b>{risk_tier}</b>. 
            A high signal can never be hidden by a high score.
        </div>""",
        unsafe_allow_html=True
    )

# Data-completeness warning
if completeness < 100:
    st.markdown(
        f"""<div style="background:#FFF8E1;border-left:4px solid {AMBER};
            border-radius:6px;padding:0.65rem 1rem;font-size:0.82rem;color:#6D4C00;
            margin-bottom:0.8rem;">
            ⚠️ <b>Incomplete data ({completeness:.0f}%):</b> {', '.join(unavailable) if unavailable else 'some indicators missing'}. 
            Missing metrics reduce assessment confidence — they do NOT imply lower risk.
        </div>""",
        unsafe_allow_html=True
    )

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_metrics, tab_alerts, tab_sector, tab_explain = st.tabs(
    ["📊 Risk Metrics", "🚨 Alerts", "🏭 Sector Concentration", "ℹ️ Methodology"]
)

with tab_metrics:
    METRIC_GROUPS = {
        "Market Sensitivity": [
            ("beta",      "Beta",          "",  "Sensitivity to broad market movements. >1.2 = alert."),
            ("volatility","Volatility",   "%",  "Historical portfolio return volatility."),
        ],
        "Downside Risk": [
            ("var_95",    "VaR 95%",      "%",  "95% Value at Risk."),
            ("var_99",    "VaR 99%",      "%",  "99% Value at Risk."),
            ("cvar_95",   "CVaR 95%",     "%",  "Conditional VaR (expected shortfall)."),
            ("max_drawdown","Max Drawdown","%", "Largest peak-to-trough decline."),
        ],
        "Risk-Adjusted Returns": [
            ("sharpe_ratio",  "Sharpe Ratio", "", "Return per unit of total risk."),
            ("sortino_ratio", "Sortino Ratio","", "Return per unit of downside risk."),
            ("tracking_error","Tracking Error","%","Deviation from benchmark returns."),
        ],
    }

    for group_name, metrics in METRIC_GROUPS.items():
        st.markdown(f"##### {group_name}")
        cols = st.columns(len(metrics))
        for col, (key, label, suffix, tip) in zip(cols, metrics):
            val = indicators.get(key, {}).get("value")
            if val is not None:
                col.metric(label, f"{val:.2f}{suffix}", help=tip)
            else:
                with col:
                    st.metric(label, "N/A", help=f"{tip} · Data not available.")
        st.markdown("")

    if unavailable:
        st.info(f"Unavailable indicators: {', '.join(unavailable)}. "
                "Their absence reduces confidence, not risk.")

with tab_alerts:
    high_alerts   = [a for a in alerts if a.get("severity") == "high"]
    medium_alerts = [a for a in alerts if a.get("severity") == "medium"]

    if not alerts:
        if risk_level == "not_assessed":
            st.warning("Risk cannot be assessed — no performance or risk metrics are available.")
        else:
            st.success("No risk alerts identified in the available data.")
    else:
        if high_alerts:
            st.markdown("##### 🔴 High Severity")
            for a in high_alerts:
                st.markdown(
                    f"""<div style="background:#FDECEA;border-left:4px solid {RED};
                    border-radius:6px;padding:0.65rem 1rem;margin-bottom:0.5rem;">
                    <b>🔴 {a.get('type','').replace('_',' ').title()}</b>: {a['message']}
                    </div>""", unsafe_allow_html=True)
        if medium_alerts:
            st.markdown("##### 🟠 Medium Severity")
            for a in medium_alerts:
                st.markdown(
                    f"""<div style="background:#FFF3CD;border-left:4px solid {AMBER};
                    border-radius:6px;padding:0.65rem 1rem;margin-bottom:0.5rem;">
                    <b>🟠 {a.get('type','').replace('_',' ').title()}</b>: {a['message']}
                    </div>""", unsafe_allow_html=True)

    dq_alerts = result.get("data_quality_alerts", [])
    if dq_alerts:
        st.markdown("##### ℹ️ Data Quality Notes")
        for a in dq_alerts:
            st.info(a.get("message", str(a)))

with tab_sector:
    conc = result.get("sector_concentration") or {}
    largest = conc.get("largest_sector") or {}
    hhi = conc.get("hhi")
    eff = conc.get("effective_number_of_sectors")
    total_eq = result.get("total_equity_exposure", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("HHI", f"{hhi:.3f}" if hhi else "N/A",
              help="0 = fully diversified, 1 = single sector. Alert if >0.3.")
    c2.metric("Effective Sectors", f"{eff:.2f}" if eff else "N/A")
    c3.metric("Total Equity Exposure", f"{total_eq:.2f}%")
    c4.metric("Largest Sector",
              largest.get("sector_name", "N/A"),
              f"{largest.get('exposure_percentage',0):.1f}%")

with tab_explain:
    st.markdown("##### Risk Score Formula")
    st.markdown(result.get("risk_score_note", "See source code."))
    st.markdown("##### Signal / Score / Tier Relationship")
    if consistency_note:
        st.markdown(
            f'<div style="background:#F0F4FA;border-radius:6px;padding:0.8rem 1rem;'
            f'font-size:0.82rem;color:{NAVY};">{consistency_note}</div>',
            unsafe_allow_html=True
        )
    st.markdown("##### Thresholds Note")
    st.caption(result.get("thresholds_note", ""))
    st.markdown("##### Data Dates")
    dates = result.get("data_dates", {})
    d1, d2 = st.columns(2)
    d1.metric("Performance Date", dates.get("performance_date") or "Unavailable")
    d2.metric("Risk Calc Date",   dates.get("risk_date") or "Unavailable")

st.markdown("---")
data_note(result.get("data_note",
    "Risk analysis uses historical dataset records. Not a live risk assessment."))
st.caption("PL Capital · Portfolio Analytics Agent")
