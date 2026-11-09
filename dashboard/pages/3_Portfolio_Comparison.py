"""
PL Capital — Portfolio Comparison
Side-by-side comparison using the existing compare_portfolios() backend.
Coverage, winner logic and no-defensible-winner outcomes are all explicit.
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
    disclaimer, data_note, badge, fmt_aum,
    GOLD, NAVY, RED, AMBER, GREEN, MID_GREY, WHITE, CHART_COLORS,
    PLATINUM,
)
inject_css()

from portfolio_comparison import compare_portfolios, MIN_COMPARABLE_METRICS, MIN_COVERAGE_PCT, MIN_WIN_MARGIN
from database import get_connection

st.set_page_config(
    page_title="Portfolio Comparison | PL Capital",
    page_icon="⚖️",
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

page_header("⚖️", "Portfolio Comparison",
            "Side-by-side analytics · Coverage-aware winner logic · Heuristic comparison")

# ── Portfolio selectors ───────────────────────────────────────────────────────
conn = get_connection()
portfolios = pd.read_sql_query(
    """SELECT portfolio_id, portfolio_name, strategy_type,
              target_risk_level, total_aum
       FROM portfolios ORDER BY portfolio_name""", conn)
conn.close()

if len(portfolios) < 2:
    st.error("At least two portfolios are required for comparison.")
    st.stop()

pnames = portfolios["portfolio_name"].tolist()
sel_col1, sel_col2 = st.columns(2)

with sel_col1:
    st.markdown(
        f'<div style="background:{NAVY};color:{GOLD};padding:0.4rem 1rem;'
        f'border-radius:6px 6px 0 0;font-weight:700;font-size:0.8rem;'
        f'text-transform:uppercase;letter-spacing:.06em;">Portfolio A</div>',
        unsafe_allow_html=True
    )
    portfolio_1 = st.selectbox("Portfolio A", pnames,
        index=pnames.index("Tech Innovation Fund") if "Tech Innovation Fund" in pnames else 0,
        label_visibility="collapsed", key="comp_a")

with sel_col2:
    st.markdown(
        f'<div style="background:#0D2044;color:{GOLD};padding:0.4rem 1rem;'
        f'border-radius:6px 6px 0 0;font-weight:700;font-size:0.8rem;'
        f'text-transform:uppercase;letter-spacing:.06em;">Portfolio B</div>',
        unsafe_allow_html=True
    )
    default_b = pnames.index("Growth Equity Fund") if "Growth Equity Fund" in pnames else 1
    portfolio_2 = st.selectbox("Portfolio B", pnames,
        index=default_b, label_visibility="collapsed", key="comp_b")

if portfolio_1 == portfolio_2:
    st.warning("Please select two different portfolios.")
    st.stop()

# ── Overview cards ─────────────────────────────────────────────────────────────
d1 = portfolios[portfolios["portfolio_name"] == portfolio_1].iloc[0]
d2 = portfolios[portfolios["portfolio_name"] == portfolio_2].iloc[0]

oc1, oc2 = st.columns(2)
for col, d, label in [(oc1, d1, "A"), (oc2, d2, "B")]:
    with col:
        st.markdown(
            f"""<div style="background:{WHITE};border-radius:8px;padding:1rem 1.25rem;
                border-left:5px solid {GOLD};box-shadow:0 1px 4px rgba(10,22,40,0.07);">
                <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:.1em;
                    color:{MID_GREY};font-weight:700;">Portfolio {label}</div>
                <div style="font-size:1.1rem;font-weight:800;color:{NAVY};">{d['portfolio_name']}</div>
                <div style="font-size:0.82rem;color:{MID_GREY};margin-top:4px;">
                    {d['strategy_type']} · Target Risk: {d['target_risk_level']} · AUM: {fmt_aum(d['total_aum'])}
                </div>
            </div>""", unsafe_allow_html=True
        )

st.markdown("---")

# ── Run comparison ─────────────────────────────────────────────────────────────
with st.spinner("Comparing portfolios…"):
    result = compare_portfolios(portfolio_1, portfolio_2)

if not result.get("success"):
    st.error(f"Comparison failed: {result.get('error')}")
    st.stop()

metrics      = result.get("performance_and_risk", {})
overall_w    = result.get("overall_winner", "")
winner_reason= result.get("winner_reason", "")
comp_n       = result.get("comparable_metrics_count", 0)
total_m      = result.get("total_metrics", 9)
coverage_pct = result.get("metric_coverage_pct", 0)
wins_1       = result.get("wins_portfolio_1", 0)
wins_2       = result.get("wins_portfolio_2", 0)
ties         = result.get("ties", 0)
unavail      = result.get("unavailable_metric_count", 0)

# ── Winner / coverage banner ───────────────────────────────────────────────────
if overall_w not in ("tie", "no_defensible_winner") and overall_w:
    win_color = GREEN
    win_icon  = "🏆"
    win_label = f"Winner: {overall_w}"
elif overall_w == "tie":
    win_color = AMBER
    win_icon  = "🤝"
    win_label = "Result: Tie"
else:
    win_color = MID_GREY
    win_icon  = "➖"
    win_label = "No Defensible Winner"

st.markdown(
    f"""<div style="background:{WHITE};border-radius:8px;padding:1rem 1.5rem;
        border-left:5px solid {win_color};box-shadow:0 1px 4px rgba(10,22,40,0.07);
        display:flex;gap:1.5rem;align-items:flex-start;margin-bottom:1rem;">
        <div style="font-size:2rem;line-height:1;">{win_icon}</div>
        <div style="flex:1">
            <div style="font-size:1.1rem;font-weight:800;color:{win_color};">{win_label}</div>
            <div style="font-size:0.82rem;color:{MID_GREY};margin-top:4px;">{winner_reason}</div>
        </div>
        <div style="text-align:right;min-width:220px;">
            <div style="font-size:0.72rem;text-transform:uppercase;color:{MID_GREY};
                letter-spacing:.06em;font-weight:700;">Metric Coverage</div>
            <div style="font-size:1.1rem;font-weight:700;color:{NAVY};">
                {comp_n}/{total_m} comparable ({coverage_pct:.0f}%)</div>
            <div style="font-size:0.72rem;color:{MID_GREY};">
                Threshold: ≥{MIN_COMPARABLE_METRICS} metrics · ≥{MIN_COVERAGE_PCT:.0f}% · margin ≥{MIN_WIN_MARGIN}</div>
            <div style="background:#E8EDF2;border-radius:4px;height:6px;margin-top:4px;">
                <div style="background:{win_color};width:{coverage_pct:.0f}%;
                    height:6px;border-radius:4px;"></div>
            </div>
        </div>
    </div>""",
    unsafe_allow_html=True
)

disclaimer(
    "This is a transparent heuristic comparison of nine correlated financial metrics. "
    "It is NOT a statistically robust investment recommendation. "
    f"A winner requires ≥{MIN_COMPARABLE_METRICS} comparable metrics, "
    f"≥{MIN_COVERAGE_PCT:.0f}% coverage, and a win margin ≥{MIN_WIN_MARGIN}."
)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_perf, tab_alloc, tab_sector, tab_quality = st.tabs(
    ["📊 Performance & Risk", "💼 Asset Allocation", "🏭 Sector Exposure", "📋 Data Quality"]
)

METRIC_BETTER = {  # True = higher is better
    "total_return_1y": True, "sharpe_ratio": True, "sortino_ratio": True,
    "volatility": False, "max_drawdown": False, "beta": False,
    "var_95": False, "cvar_95": False, "tracking_error": False,
}

with tab_perf:
    # Score summary row
    s1, s2, s3 = st.columns(3)
    s1.metric(f"Wins — {portfolio_1[:20]}", wins_1)
    s2.metric(f"Wins — {portfolio_2[:20]}", wins_2)
    s3.metric("Ties / Unavailable", f"{ties} / {unavail}")

    # Per-metric table
    rows = []
    for key, item in metrics.items():
        v1 = item.get("portfolio_1")
        v2 = item.get("portfolio_2")
        diff = item.get("difference")
        winner = item.get("winner", "unavailable")
        w1_flag = "✓" if winner == "portfolio_1" else ""
        w2_flag = "✓" if winner == "portfolio_2" else ""
        avail = item.get("availability", "")
        rows.append({
            "Metric": item["label"],
            f"{portfolio_1[:22]}": f"{v1:.2f}{item['unit']}" if v1 is not None else "N/A",
            "Win A": w1_flag,
            f"{portfolio_2[:22]}": f"{v2:.2f}{item['unit']}" if v2 is not None else "N/A",
            "Win B": w2_flag,
            "Diff (A−B)": f"{diff:+.2f}{item['unit']}" if diff is not None else "—",
            "Better": "↑ Higher" if METRIC_BETTER.get(key, True) else "↓ Lower |abs|",
            "Status": "Available" if avail == "available" else "Insufficient Data",
        })
    comp_df = pd.DataFrame(rows)
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    # Bar chart: return + volatility
    chart_data = []
    for key, label in [("total_return_1y", "1Y Return"), ("volatility", "Volatility"),
                        ("sharpe_ratio", "Sharpe"), ("sortino_ratio", "Sortino")]:
        item = metrics.get(key, {})
        for pkey, pname in [("portfolio_1", portfolio_1), ("portfolio_2", portfolio_2)]:
            v = item.get(pkey)
            if v is not None:
                chart_data.append({"Metric": label, "Portfolio": pname[:25], "Value": v})
    if chart_data:
        fig_c = px.bar(pd.DataFrame(chart_data), x="Metric", y="Value",
                       color="Portfolio", barmode="group",
                       color_discrete_sequence=[GOLD, "#4E79A7"],
                       text_auto=".2f")
        fig_c.update_layout(
            height=320, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
            font=dict(color=NAVY), margin=dict(l=5, r=5, t=10, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.01),
        )
        st.plotly_chart(fig_c, use_container_width=True)

with tab_alloc:
    alloc_cmp = result.get("asset_allocation_comparison", {})
    if alloc_cmp:
        alloc_rows = []
        for asset, vals in alloc_cmp.items():
            v1_avail = vals.get("portfolio_1_available", True)
            v2_avail = vals.get("portfolio_2_available", True)
            alloc_rows.append({
                "Asset Type": asset,
                portfolio_1[:25]: f"{vals['portfolio_1']:.1f}%" if vals.get("portfolio_1") is not None else "N/A (unavail.)",
                portfolio_2[:25]: f"{vals['portfolio_2']:.1f}%" if vals.get("portfolio_2") is not None else "N/A (unavail.)",
                "Diff": f"{vals['difference']:+.2f}%" if vals.get("difference") is not None else "—",
            })
        alloc_df = pd.DataFrame(alloc_rows)
        st.dataframe(alloc_df, use_container_width=True, hide_index=True)

        chart_a = []
        for asset, vals in alloc_cmp.items():
            for pkey, pname in [("portfolio_1", portfolio_1), ("portfolio_2", portfolio_2)]:
                v = vals.get(pkey)
                if v is not None:
                    chart_a.append({"Asset": asset, "Portfolio": pname[:25], "Pct": v})
        if chart_a:
            fig_a = px.bar(pd.DataFrame(chart_a), x="Asset", y="Pct",
                           color="Portfolio", barmode="group",
                           color_discrete_sequence=[GOLD, "#4E79A7"],
                           text_auto=".1f",
                           labels={"Pct": "Allocation (%)", "Asset": ""})
            fig_a.update_layout(height=280, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                                font=dict(color=NAVY), margin=dict(t=10))
            st.plotly_chart(fig_a, use_container_width=True)
    else:
        st.info("Asset allocation comparison not available.")
    disclaimer("Actual zero (no holdings in that asset class) is distinguished from "
               "'unavailable' (no allocation data for that portfolio).")

with tab_sector:
    sec_cmp = result.get("sector_exposure_comparison", {})
    if sec_cmp:
        sec_rows = []
        for sec, vals in sec_cmp.items():
            sec_rows.append({
                "Sector": sec,
                portfolio_1[:25]: f"{vals['portfolio_1']:.1f}%" if vals.get("portfolio_1") is not None else "N/A",
                portfolio_2[:25]: f"{vals['portfolio_2']:.1f}%" if vals.get("portfolio_2") is not None else "N/A",
                "Diff": f"{vals['difference']:+.2f}%" if vals.get("difference") is not None else "—",
            })
        sec_df = pd.DataFrame(sec_rows)
        st.dataframe(sec_df, use_container_width=True, hide_index=True)

        chart_s = []
        for sec, vals in sec_cmp.items():
            for pkey, pname in [("portfolio_1", portfolio_1), ("portfolio_2", portfolio_2)]:
                v = vals.get(pkey)
                if v is not None:
                    chart_s.append({"Sector": sec[:20], "Portfolio": pname[:25], "Pct": v})
        if chart_s:
            fig_s = px.bar(pd.DataFrame(chart_s), x="Sector", y="Pct",
                           color="Portfolio", barmode="group",
                           color_discrete_sequence=[GOLD, "#4E79A7"],
                           text_auto=".1f",
                           labels={"Pct": "Equity Exposure (%)", "Sector": ""})
            fig_s.update_layout(height=320, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                                font=dict(color=NAVY), margin=dict(t=10, b=40),
                                xaxis_tickangle=-35)
            st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("Sector exposure comparison not available.")

with tab_quality:
    dq = result.get("data_quality", {})
    dates = result.get("data_dates", {})
    conc_cmp = result.get("concentration_comparison", {})

    q_col1, q_col2 = st.columns(2)
    for q_col, pk, pname in [(q_col1, "portfolio_1", portfolio_1),
                              (q_col2, "portfolio_2", portfolio_2)]:
        with q_col:
            st.markdown(f"**{pname}**")
            d = dq.get(pk, {})
            st.write(f"Analysis Status: **{str(d.get('analysis_status','—')).replace('_',' ').title()}**")
            unalloc = d.get("unallocated_allocation")
            st.write(f"Unallocated: {unalloc:.2f}%" if unalloc is not None else "Unallocated: N/A")
            miss_sec = d.get("missing_sector_exposure")
            st.write(f"Missing Sector Exposure: {miss_sec:.2f}%" if miss_sec is not None else "Missing Sector: N/A")
            perf_date = dates.get(f"{pk}_performance_date")
            risk_date = dates.get(f"{pk}_risk_date")
            st.caption(f"Performance date: {perf_date or 'N/A'} · Risk date: {risk_date or 'N/A'}")

    if conc_cmp:
        st.markdown("##### Concentration Comparison")
        hhi = conc_cmp.get("hhi", {})
        eff = conc_cmp.get("effective_number_of_sectors", {})
        cc1, cc2 = st.columns(2)
        cc1.metric(f"HHI — {portfolio_1[:20]}",
                   f"{hhi.get('portfolio_1'):.3f}" if hhi.get("portfolio_1") else "N/A")
        cc1.metric(f"HHI — {portfolio_2[:20]}",
                   f"{hhi.get('portfolio_2'):.3f}" if hhi.get("portfolio_2") else "N/A")
        cc2.metric(f"Effective Sectors — {portfolio_1[:20]}",
                   f"{eff.get('portfolio_1'):.2f}" if eff.get("portfolio_1") else "N/A")
        cc2.metric(f"Effective Sectors — {portfolio_2[:20]}",
                   f"{eff.get('portfolio_2'):.2f}" if eff.get("portfolio_2") else "N/A")

st.markdown("---")
data_note(result.get("data_note", "Comparisons use historical dataset records."))
st.caption("PL Capital · Portfolio Analytics Agent")
