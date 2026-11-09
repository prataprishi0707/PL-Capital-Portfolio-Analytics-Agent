"""
PL Capital Dashboard — Shared Theme & Utilities
All styling constants, CSS injection, and reusable UI helpers live here.
No financial calculations are performed here.
"""

import streamlit as st

# ─── Brand colours ────────────────────────────────────────────────────────────
NAVY       = "#0A1628"
DARK_BLUE  = "#0D2044"
GOLD       = "#C9A84C"
GOLD_LIGHT = "#E8C97A"
PLATINUM   = "#E8EDF2"
MID_GREY   = "#8A9BB5"
LIGHT_GREY = "#F4F6F9"
WHITE      = "#FFFFFF"

# Semantic colours (match Streamlit's own palette roughly)
RED    = "#D94F4F"
AMBER  = "#E8913A"
GREEN  = "#2E8B57"
TEAL   = "#1F7A8C"
PURPLE = "#6B4FA0"

# Chart colour sequence
CHART_COLORS = [GOLD, TEAL, "#4E79A7", "#59A14F", PURPLE, AMBER,
                "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"]

# ─── CSS ──────────────────────────────────────────────────────────────────────
GLOBAL_CSS = f"""
<style>
/* ── Root overrides ── */
:root {{
    --primary:    {NAVY};
    --accent:     {GOLD};
    --text-main:  {NAVY};
    --text-muted: {MID_GREY};
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: {NAVY} !important;
    border-right: 2px solid {GOLD} !important;
}}
[data-testid="stSidebar"] * {{
    color: {PLATINUM} !important;
}}
[data-testid="stSidebar"] a:hover {{
    color: {GOLD} !important;
}}

/* Main content background */
.stApp {{
    background: {LIGHT_GREY};
}}
.main .block-container {{
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}}

/* KPI metric cards */
[data-testid="metric-container"] {{
    background: {WHITE};
    border-radius: 8px;
    padding: 1rem 1.25rem;
    border-left: 4px solid {GOLD};
    box-shadow: 0 1px 4px rgba(10,22,40,0.08);
}}
[data-testid="metric-container"] label {{
    font-size: 0.78rem !important;
    color: {MID_GREY} !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-size: 1.55rem !important;
    font-weight: 700;
    color: {NAVY} !important;
}}

/* Page header strip */
.pl-header {{
    background: linear-gradient(135deg, {NAVY} 0%, {DARK_BLUE} 100%);
    border-radius: 10px;
    padding: 1.1rem 1.6rem;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    border-left: 5px solid {GOLD};
}}
.pl-header-title {{
    color: {WHITE};
    font-size: 1.45rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: 0.02em;
}}
.pl-header-sub {{
    color: {MID_GREY};
    font-size: 0.85rem;
    margin: 0;
}}

/* Section card wrapper */
.pl-card {{
    background: {WHITE};
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 4px rgba(10,22,40,0.07);
    border-top: 3px solid {GOLD};
}}

/* Status badges */
.badge {{
    display: inline-block;
    padding: 0.2em 0.65em;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
.badge-matched    {{ background: #D4EDDA; color: #1A5C2A; }}
.badge-obs        {{ background: #FFF3CD; color: #7D5A00; }}
.badge-disc       {{ background: #FDECEA; color: #8B1A1A; }}
.badge-incomplete {{ background: #E8EEF5; color: #3A4E68; }}
.badge-invalid    {{ background: #F3E8FF; color: #4A1070; }}
.badge-high       {{ background: #FDECEA; color: #8B1A1A; }}
.badge-moderate   {{ background: #FFF3CD; color: #7D5A00; }}
.badge-low        {{ background: #D4EDDA; color: #1A5C2A; }}
.badge-na         {{ background: #E8EDF2; color: #556070; }}

/* Disclaimer banners */
.pl-disclaimer {{
    background: #EFF4FA;
    border-left: 4px solid {MID_GREY};
    border-radius: 6px;
    padding: 0.6rem 1rem;
    font-size: 0.8rem;
    color: {MID_GREY};
    margin-top: 0.8rem;
}}

/* Data-origin label */
.data-origin {{
    font-size: 0.72rem;
    color: {MID_GREY};
    font-style: italic;
}}

/* Sidebar nav section headers */
.nav-section {{
    color: {GOLD} !important;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.3rem 0 0.1rem 0;
    border-bottom: 1px solid rgba(201,168,76,0.3);
    margin-bottom: 0.4rem;
}}

/* Consistent table styling */
.stDataFrame {{
    border-radius: 6px;
    overflow: hidden;
}}
</style>
"""


def inject_css():
    """Inject global PL Capital CSS into the current page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = ""):
    """Render the dark branded page header strip."""
    sub_html = f'<p class="pl-header-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""<div class="pl-header">
            <span style="font-size:1.8rem">{icon}</span>
            <div>
              <p class="pl-header-title">{title}</p>
              {sub_html}
            </div>
        </div>""",
        unsafe_allow_html=True
    )


def card_start():
    """Open a white card div."""
    st.markdown('<div class="pl-card">', unsafe_allow_html=True)


def card_end():
    """Close a white card div."""
    st.markdown("</div>", unsafe_allow_html=True)


def badge(text: str, kind: str) -> str:
    """Return an HTML badge span. kind: matched|obs|disc|incomplete|invalid|high|moderate|low|na"""
    cls_map = {
        "matched": "badge-matched", "observation": "badge-obs",
        "obs": "badge-obs", "discrepancy": "badge-disc",
        "disc": "badge-disc", "incomplete": "badge-incomplete",
        "invalid": "badge-invalid", "high": "badge-high",
        "moderate": "badge-moderate", "low": "badge-low",
        "na": "badge-na",
    }
    css = cls_map.get(kind.lower(), "badge-na")
    return f'<span class="badge {css}">{text}</span>'


def disclaimer(text: str):
    st.markdown(f'<div class="pl-disclaimer">ℹ️ {text}</div>', unsafe_allow_html=True)


def data_note(text: str):
    st.markdown(f'<p class="data-origin">⚡ {text}</p>', unsafe_allow_html=True)


def metric_na(label: str):
    """Show a greyed-out N/A metric."""
    st.metric(label, "N/A", help="Data not available for this portfolio.")


def sidebar_logo():
    """Render the PL Capital brand block in the sidebar."""
    st.sidebar.markdown(
        f"""
        <div style="text-align:center; padding: 1.2rem 0.5rem 0.8rem 0.5rem;">
            <div style="font-size:2rem;">📊</div>
            <div style="color:#C9A84C; font-size:1.15rem; font-weight:800;
                        letter-spacing:0.06em;">PL CAPITAL</div>
            <div style="color:#8A9BB5; font-size:0.72rem; letter-spacing:0.12em;
                        text-transform:uppercase;">Portfolio Intelligence</div>
        </div>
        <hr style="border-color:rgba(201,168,76,0.3); margin:0 0 0.8rem 0;">
        """,
        unsafe_allow_html=True
    )


def sidebar_nav_section(title: str):
    st.sidebar.markdown(
        f'<div class="nav-section">{title}</div>',
        unsafe_allow_html=True
    )


def risk_level_badge_html(risk_level: str) -> str:
    label_map = {
        "high": "HIGH RISK",
        "moderate": "MODERATE",
        "lower_observed_signals": "LOWER SIGNALS",
        "not_assessed": "NOT ASSESSED",
    }
    kind_map = {
        "high": "high",
        "moderate": "moderate",
        "lower_observed_signals": "low",
        "not_assessed": "na",
    }
    lbl = label_map.get(risk_level, risk_level.upper())
    knd = kind_map.get(risk_level, "na")
    return badge(lbl, knd)


def tier_color(tier: str) -> str:
    return {"conservative": GREEN, "moderate": AMBER, "aggressive": RED,
            "not_assessed": MID_GREY}.get(tier, MID_GREY)


def health_color(tier: str) -> str:
    return {"healthy": GREEN, "moderate": AMBER,
            "attention_needed": RED}.get(tier, MID_GREY)


def fmt_aum(value) -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"₹{value/1_000_000:.1f}M"
    return f"₹{value:,.0f}"


def get_route_label(route_value) -> str:
    """
    Return a display label for the AI agent routing path.

    This is the single source of truth used by both the AI Analyst dashboard
    page and the route-label tests. Tests must call this function directly
    rather than re-implementing the logic.

    Parameters
    ----------
    route_value : str or None
        The 'route' key from the agent response dict.
        'offline' → offline deterministic label.
        'llm'     → Gemini LLM label.
        anything else (absent, empty, None, unknown) → neutral label.

    Returns
    -------
    str : one of three display labels
    """
    if route_value == "offline":
        return "🔵 Offline deterministic route"
    if route_value == "llm":
        return "🟣 Gemini LLM route"
    return "🔧 Tool execution"
