"""
PL Capital — Portfolio Reconciliation
Compares recorded holding weights against market-value-computed weights.
Displays all statuses, discrepancies and invalid data honestly.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pl_theme import (
    inject_css, page_header, sidebar_logo, sidebar_nav_section,
    disclaimer, data_note, badge,
    GOLD, NAVY, RED, AMBER, GREEN, MID_GREY, WHITE, CHART_COLORS,
)
inject_css()

from reconciliation import (
    reconcile_portfolio,
    STATUS_MATCHED, STATUS_OBSERVATION, STATUS_DISCREPANCY,
    STATUS_INCOMPLETE, STATUS_INVALID,
)
from database import get_connection

st.set_page_config(
    page_title="Reconciliation | PL Capital",
    page_icon="🔍",
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

page_header("🔍", "Portfolio Reconciliation",
            "Weight drift analysis · Allocation integrity · AUM coverage · Data quality")

# ── Status hierarchy reference ──────────────────────────────────────────────
with st.expander("Status Hierarchy Reference", expanded=False):
    st.markdown(
        """
| Status | Meaning |
|---|---|
| **MATCHED** | All holdings comparable and within warning threshold (< 0.5 pp drift) |
| **OBSERVATION** | Some holdings exceed the warning threshold (> 0.5 pp) but none the error threshold |
| **DISCREPANCY FOUND** | One or more holdings exceed the error threshold (> 2.0 pp), or recorded weights do not sum to 1.0 |
| **INCOMPLETE** | Required inputs (price, quantity, or recorded weight) are missing; partial denominators are not normalised |
| **INVALID DATA** | A required field contains NaN, infinity, a disallowed negative, or an invalid value |

**Partial denominator rule:** Market-value weights are only computed when EVERY holding has valid quantity, price and recorded weight. Incomplete denominators are never normalised.  
**AUM coverage** is informational only — divergence between market value and AUM is expected when prices have moved since weights were calibrated.
        """
    )

# ── Portfolio selector ────────────────────────────────────────────────────────
conn = get_connection()
portfolios = pd.read_sql_query(
    "SELECT portfolio_name FROM portfolios ORDER BY portfolio_name", conn)
conn.close()

sel_col, btn_col = st.columns([3, 1])
with sel_col:
    selected = st.selectbox("Portfolio", portfolios["portfolio_name"].tolist(),
                            label_visibility="collapsed")
    st.caption("Select portfolio then click Run Reconciliation")
with btn_col:
    run = st.button("▶ Run Reconciliation", type="primary", use_container_width=True)

if not run:
    st.info("Select a portfolio and click **Run Reconciliation** to begin.")
    st.stop()

# ── Run reconciliation ────────────────────────────────────────────────────────
with st.spinner(f"Reconciling {selected}…"):
    result = reconcile_portfolio(selected)

if not result.get("success"):
    st.error(f"Reconciliation failed: {result.get('error')}")
    st.stop()

status = result["status"]
legacy = result["reconciliation_status"]

# ── Status banner ─────────────────────────────────────────────────────────────
STATUS_CONFIG = {
    STATUS_MATCHED:     (GREEN,    "✅", "All holdings reconcile within thresholds."),
    STATUS_OBSERVATION: (AMBER,    "⚠️", "One or more holdings exceed the warning threshold (>0.5 pp)."),
    STATUS_DISCREPANCY: (RED,      "❌", "One or more holdings exceed the error threshold (>2.0 pp)."),
    STATUS_INCOMPLETE:  (MID_GREY, "⚪", "Required inputs are missing; market-value weights cannot be computed for all holdings."),
    STATUS_INVALID:     ("#6B4FA0","⛔", "One or more inputs are invalid (NaN, infinity, negative, or unparseable). Results are not trustworthy."),
}
s_color, s_icon, s_msg = STATUS_CONFIG.get(status, (MID_GREY, "ℹ️", "Status unknown."))
mdc = result.get("market_denominator_complete", False)
aa  = result.get("allocation_assessable", False)

st.markdown(
    f"""<div style="background:{WHITE};border-radius:10px;padding:1.1rem 1.5rem;
        border-left:6px solid {s_color};box-shadow:0 1px 6px rgba(10,22,40,0.09);
        display:flex;gap:1.2rem;align-items:flex-start;margin-bottom:1rem;">
        <div style="font-size:2rem;">{s_icon}</div>
        <div style="flex:1">
            <div style="font-size:1.1rem;font-weight:800;color:{s_color};">{status}</div>
            <div style="font-size:0.82rem;color:{MID_GREY};">{s_msg}</div>
        </div>
        <div style="text-align:right;min-width:230px;">
            <div style="font-size:0.7rem;text-transform:uppercase;color:{MID_GREY};
                letter-spacing:.06em;font-weight:700;">Denominator Completeness</div>
            <div style="font-size:0.82rem;color:{NAVY};margin-top:2px;">
                Market-value: {'<b style="color:' + GREEN + '">Complete</b>' if mdc else '<b style="color:' + RED + '">Incomplete</b>'} &nbsp;|&nbsp;
                Allocation: {'<b style="color:' + GREEN + '">Assessable</b>' if aa else '<b style="color:' + RED + '">Not assessable</b>'}
            </div>
            <div style="font-size:0.72rem;color:{MID_GREY};margin-top:4px;">
                Data completeness: {result.get('data_completeness_pct',0):.0f}% of holdings fully comparable
            </div>
        </div>
    </div>""",
    unsafe_allow_html=True
)

# ── Validation errors (invalid data banner) ────────────────────────────────────
verrs = result.get("validation_errors", [])
if verrs:
    st.markdown(
        f"""<div style="background:#F3E8FF;border-left:5px solid #6B4FA0;border-radius:6px;
            padding:0.8rem 1.2rem;margin-bottom:1rem;">
            <b>⛔ {len(verrs)} Validation Error(s)</b>
        </div>""", unsafe_allow_html=True
    )
    for ve in verrs:
        lvl = ve.get("level", "holding")
        sym = ve.get("symbol", "?")
        errors = ve.get("errors", {})
        for field, msg in errors.items():
            st.error(f"{'Portfolio-level' if lvl=='portfolio' else sym} · `{field}`: {msg}")

# ── KPI row ───────────────────────────────────────────────────────────────────
s = result["summary"]
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Holdings", s["total_holdings"])
k2.metric("✅ Matched",       s["matched_count"])
k3.metric("⚠️ Observations",  s["observation_count"])
k4.metric("❌ Discrepancies", s["discrepancy_count"])
k5.metric("⚪ Incomplete",    s["incomplete_count"])
k6.metric("⛔ Invalid",       s["invalid_count"])

# ── Two-axis panel ────────────────────────────────────────────────────────────
ax1, ax2 = st.columns(2)

with ax1:
    st.markdown("##### Allocation Drift (Weights vs 1.0)")
    ad = result.get("allocation_drift", {})
    ad_status = ad.get("status", "—")
    ad_total  = ad.get("recorded_total_weight")
    ad_drift  = ad.get("drift")
    if ad_status == STATUS_MATCHED:
        st.success(f"Recorded weights sum = {ad_total} (drift {ad_drift:.4f} — within threshold)")
    elif ad_status == STATUS_OBSERVATION:
        st.warning(f"Weights sum = {ad_total} (drift {ad_drift:.4f} — warning threshold exceeded)")
    elif ad_status == STATUS_DISCREPANCY:
        st.error(f"Weights sum = {ad_total} (drift {ad_drift:.4f} — error threshold exceeded)")
    elif ad_status == STATUS_INCOMPLETE:
        st.info("Allocation drift cannot be assessed — some recorded weights are missing or invalid. "
                "A partial weight set is never summed.")
    else:
        st.info(f"Allocation drift status: {ad_status}")

with ax2:
    st.markdown("##### AUM Coverage (Market Value vs Recorded AUM) — Informational")
    aum = result.get("aum_coverage", {})
    aum_status = aum.get("status", "—")
    cov_pct    = aum.get("coverage_pct")
    rec_aum    = aum.get("recorded_aum")
    mkt_val    = aum.get("total_market_value")
    aum_vstatus= aum.get("aum_status", "")

    if aum_status == STATUS_INVALID:
        st.error(f"Recorded AUM is invalid ({aum_vstatus}): {aum.get('note','')}")
    elif aum_status == STATUS_INCOMPLETE:
        st.info(aum.get("note", "AUM coverage cannot be assessed from a partial market value."))
    elif aum_status == "not_assessed":
        st.info(aum.get("note", "AUM is missing or zero."))
    elif cov_pct is not None:
        if aum_status == STATUS_OBSERVATION:
            st.warning(f"Coverage: {cov_pct:.1f}% · Market value ₹{mkt_val:,.0f} vs AUM ₹{rec_aum:,.0f}")
        else:
            st.success(f"Coverage: {cov_pct:.1f}% · Market value ₹{mkt_val:,.0f} vs AUM ₹{rec_aum:,.0f}")
        st.caption(aum.get("note", ""))

st.markdown("---")

# ── Holdings detail ────────────────────────────────────────────────────────────
tab_holdings, tab_disc, tab_costbasis = st.tabs(
    ["📋 Holdings Detail", "⚠️ Discrepancies", "🔬 Cost-Basis Diagnostic"]
)

STATUS_LABEL = {
    STATUS_MATCHED:     "✅ Matched",
    STATUS_OBSERVATION: "⚠️ Observation",
    STATUS_DISCREPANCY: "❌ Discrepancy",
    STATUS_INCOMPLETE:  "⚪ Incomplete",
    STATUS_INVALID:     "⛔ Invalid",
}

with tab_holdings:
    holdings = result.get("holdings", [])
    if holdings:
        h_rows = []
        for h in holdings:
            h_rows.append({
                "Symbol":        h.get("symbol", "?"),
                "Company":       h.get("company_name", ""),
                "Type":          h.get("asset_type", ""),
                "Qty":           h.get("quantity"),
                "Price":         h.get("current_price"),
                "Mkt Value":     h.get("market_value"),
                "Rec. Weight":   h.get("recorded_weight"),
                "Comp. Weight":  h.get("computed_weight"),
                "Drift (pp)":    h.get("weight_drift_pct"),
                "Status":        STATUS_LABEL.get(h.get("status"), h.get("status", "?")),
            })
        h_df = pd.DataFrame(h_rows)
        st.dataframe(h_df, use_container_width=True, hide_index=True)

        # Drift chart (only where drift is computable)
        drift_data = [r for r in h_rows if r["Drift (pp)"] is not None]
        if drift_data:
            drift_df = pd.DataFrame(drift_data)
            STATUS_COLOR_MAP = {
                "✅ Matched": GREEN, "⚠️ Observation": AMBER,
                "❌ Discrepancy": RED, "⚪ Incomplete": MID_GREY,
                "⛔ Invalid": "#6B4FA0",
            }
            drift_df["_color"] = drift_df["Status"].map(STATUS_COLOR_MAP).fillna(MID_GREY)
            fig_d = px.bar(
                drift_df, x="Symbol", y="Drift (pp)", color="Status",
                color_discrete_map=STATUS_COLOR_MAP,
                title="Weight Drift per Holding (percentage points)",
                labels={"Drift (pp)": "Drift (pp)"},
            )
            fig_d.update_layout(
                height=320, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                font=dict(color=NAVY), margin=dict(t=30, b=40),
                xaxis_tickangle=-35,
            )
            st.plotly_chart(fig_d, use_container_width=True)
    else:
        st.info("No holdings detail available.")

with tab_disc:
    discrepancies = result.get("discrepancies", [])
    holding_disc = [d for d in discrepancies if d.get("type") != "allocation_drift"]
    alloc_flags  = [d for d in discrepancies if d.get("type") == "allocation_drift"]

    if not discrepancies:
        st.success("No discrepancies detected.")
    else:
        for d in alloc_flags:
            st.error(
                f"**Allocation drift [{d['severity'].upper()}]:** "
                f"Recorded total = {d['recorded_total']} · Drift = {d['drift']:.4f} · Expected = 1.0"
            )
        if holding_disc:
            d_rows = []
            for d in sorted(holding_disc,
                            key=lambda x: abs(x.get("weight_drift_pct") or 0),
                            reverse=True):
                cb = d.get("cost_basis_weight")
                d_rows.append({
                    "Symbol":         d.get("symbol","?"),
                    "Recorded Wt":    d.get("recorded_weight"),
                    "Computed Wt (mkt)": d.get("computed_weight"),
                    "Cost-Basis Wt (diag)": f"{cb:.4f}" if cb is not None else "N/A",
                    "Drift (pp)":     d.get("weight_drift_pct"),
                    "Severity":       d.get("severity","?").upper(),
                })
            disc_df = pd.DataFrame(d_rows)
            st.dataframe(disc_df, use_container_width=True, hide_index=True)

with tab_costbasis:
    cb_complete = result.get("cost_basis_denominator_complete", False)
    total_cb    = result.get("total_cost_basis")
    if not cb_complete:
        st.info(
            "Cost-basis diagnostic is unavailable: one or more holdings have missing or "
            "invalid cost_basis values. A partial cost-basis set is never normalised."
        )
    elif total_cb is not None:
        st.success(f"Cost-basis denominator complete · Total cost basis: ₹{total_cb:,.2f}")
        cb_rows = []
        for h in result.get("holdings", []):
            cb_w = h.get("cost_basis_weight")
            cb_rows.append({
                "Symbol":           h.get("symbol","?"),
                "Cost Basis":       h.get("cost_basis"),
                "Cost-Basis Weight": f"{cb_w:.4f}" if cb_w is not None else "N/A",
                "Recorded Weight":  h.get("recorded_weight"),
            })
        cb_df = pd.DataFrame(cb_rows)
        st.dataframe(cb_df, use_container_width=True, hide_index=True)
        disclaimer(
            "Cost-basis weight = cost_basis / Σ(cost_basis). "
            "This is a DIAGNOSTIC comparison — not historical truth. "
            "cost_basis reflects recorded purchase values, not the AUM-scaling basis."
        )
    else:
        st.info("Cost-basis total could not be computed.")

# ── Data issues ────────────────────────────────────────────────────────────────
dupes    = result.get("duplicate_securities", [])
zeros    = result.get("zero_weight_holdings", [])
unpriced = result.get("unpriced_holdings", [])

if dupes or zeros or unpriced:
    st.markdown("---")
    st.markdown("##### Data Quality Issues")
    if dupes:
        st.warning(f"Duplicate securities: {', '.join(dupes)}")
    if zeros:
        st.warning(f"Zero-weight holdings: {', '.join(zeros)}")
    if unpriced:
        st.info(f"Holdings without current_price (excluded from market-value computation): {', '.join(unpriced)}")

st.markdown("---")
t = result.get("thresholds", {})
data_note(
    f"Formula: computed_weight = (qty × current_price) / Σ(qty × current_price). "
    f"Warning > {t.get('warning_threshold_pct', 0.5):.1f} pp · "
    f"Error > {t.get('error_threshold_pct', 2.0):.1f} pp. "
    f"{result.get('data_note','')}"
)
st.caption("PL Capital · Portfolio Analytics Agent")
