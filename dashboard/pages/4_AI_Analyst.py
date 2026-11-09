"""
PL Capital — AI Analyst
Conversational portfolio analytics powered by Gemini function calling.
Preserves the existing secure SQL validation, tool-calling pipeline,
hybrid offline routing, and conversation history.
"""

import os
import sys
import json
from pathlib import Path
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pl_theme import (
    inject_css, page_header, sidebar_logo, sidebar_nav_section,
    disclaimer, data_note, badge, get_route_label,
    GOLD, NAVY, RED, AMBER, GREEN, MID_GREY, WHITE,
)
inject_css()

from agent import ask_portfolio_agent
from main import get_schema_description

st.set_page_config(
    page_title="AI Analyst | PL Capital",
    page_icon="🤖",
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

page_header("🤖", "AI Analyst",
            "Natural-language portfolio analytics · Gemini function calling · Hybrid routing")

# ── Sidebar: capabilities + examples ─────────────────────────────────────────
st.sidebar.markdown("---")
sidebar_nav_section("CAPABILITIES")
for t in ["SQL Query Tool", "Sector Exposure Calculator", "Portfolio Health Analyzer",
          "Portfolio Comparison", "Risk Intelligence", "Reconciliation Engine"]:
    st.sidebar.caption(f"◆ {t}")

EXAMPLES = [
    "How many portfolios are in the database?",
    "What are the sector exposures for the Tech Innovation Fund?",
    "Analyze the health of the Balanced Portfolio.",
    "Compare Tech Innovation Fund and Growth Equity Fund.",
    "Show me the risk profile of the Emerging Markets Fund.",
    "List the top 5 holdings by cost basis in the Growth Equity Fund.",
    "What is the total AUM across all high-risk portfolios?",
    "Reconcile the holdings of the Balanced Portfolio.",
]

st.sidebar.markdown("---")
sidebar_nav_section("EXAMPLE QUESTIONS")
for q in EXAMPLES:
    st.sidebar.caption(f"• {q}")

# ── API config ────────────────────────────────────────────────────────────────
def get_api_key():
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        return key
    try:
        from google.colab import userdata
        return userdata.get("PlCapitals")
    except Exception:
        return None

# Override via GEMINI_MODEL env var.
# Default: gemini-2.5-flash — verified present in google-genai SDK 1.64.0 source.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

api_key = get_api_key()
offline_mode = api_key is None

if offline_mode:
    st.markdown(
        f"""<div style="background:#FFF8E1;border-left:5px solid {AMBER};border-radius:6px;
            padding:0.8rem 1.2rem;margin-bottom:1rem;">
            <b>⚠️ Demo Mode — No API Key</b><br>
            <span style="font-size:0.82rem;color:{MID_GREY};">
            Set the <code>GOOGLE_API_KEY</code> environment variable to enable full AI analysis.
            In Demo Mode, offline deterministic routing handles supported query patterns
            (portfolio count, sector exposure, risk analysis, comparisons) without the
            Gemini API. Complex or ambiguous queries will not be answered.
            </span></div>""",
        unsafe_allow_html=True
    )
else:
    try:
        from google import genai as _genai
        client = _genai.Client(api_key=api_key)
        st.markdown(
            f"""<div style="background:#D4EDDA;border-left:5px solid {GREEN};border-radius:6px;
                padding:0.6rem 1rem;margin-bottom:1rem;font-size:0.82rem;">
                ✅ Gemini API connected · Model: <code>{MODEL_NAME}</code>
            </div>""", unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Failed to initialise Gemini client: {e}")
        offline_mode = True
        client = None

# ── Session state ─────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Suggestion buttons (shown before first message) ───────────────────────────
if not st.session_state.chat_history:
    st.markdown("#### Try one of these questions:")
    cols = st.columns(4)
    for i, q in enumerate(EXAMPLES[:8]):
        if cols[i % 4].button(q, key=f"sugg_{i}", use_container_width=True):
            st.session_state.pending_question = q
            st.rerun()

# ── Chat history display ──────────────────────────────────────────────────────
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                # Use the shared helper from pl_theme — single source of truth.
                route_indicator = get_route_label(msg.get("route"))
                with st.expander(
                    f"{route_indicator} · {len(tool_calls)} tool call(s)",
                    expanded=False
                ):
                    for idx, call in enumerate(tool_calls, 1):
                        st.markdown(f"**Tool {idx}: `{call.get('name')}`**")
                        args = call.get("arguments", {})
                        if args:
                            st.json(args)
                        sql = call.get("generated_sql")
                        if sql:
                            st.markdown("**Generated SQL:**")
                            st.code(sql, language="sql")
                        res = call.get("result")
                        if res is not None:
                            with st.expander("Raw tool result", expanded=False):
                                st.json(res)
                        if idx < len(tool_calls):
                            st.divider()

# ── Chat input ────────────────────────────────────────────────────────────────
user_q = st.chat_input("Ask a portfolio analytics question…")
if st.session_state.pending_question:
    user_q = st.session_state.pending_question
    st.session_state.pending_question = None

# ── Clear button ──────────────────────────────────────────────────────────────
if st.session_state.chat_history:
    if st.button("🗑️ Clear conversation", type="secondary"):
        st.session_state.chat_history = []
        st.rerun()

# ── Process question ──────────────────────────────────────────────────────────
if user_q:
    st.session_state.chat_history.append({"role": "user", "content": user_q})
    with st.chat_message("user"):
        st.markdown(user_q)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("⏳ Analysing your question…")

        try:
            if offline_mode:
                from agent import ask_portfolio_agent
                schema = get_schema_description()
                response = ask_portfolio_agent(
                    user_question=user_q,
                    client=None,
                    model_name=MODEL_NAME,
                    schema_description=schema,
                    return_details=True,
                    conversation_history=st.session_state.chat_history[:-1],
                )
            else:
                schema = get_schema_description()
                response = ask_portfolio_agent(
                    user_question=user_q,
                    client=client,
                    model_name=MODEL_NAME,
                    schema_description=schema,
                    return_details=True,
                    conversation_history=st.session_state.chat_history[:-1],
                )

            answer = response.get("answer", "No answer generated.")
            tool_calls = response.get("tool_calls", [])
            # Initialise route BEFORE the tool_calls check so it is always
            # defined, even when the agent answers without invoking any tool.
            route = response.get("route", "")

            placeholder.markdown(answer)

            if tool_calls:
                # Use the shared helper from pl_theme — single source of truth.
                route_label = get_route_label(route)
                # Routing note
                st.markdown(
                    f'<div style="font-size:0.72rem;color:{MID_GREY};margin-top:4px;">'
                    f'{route_label} · Tool-derived result</div>',
                    unsafe_allow_html=True
                )
                with st.expander(
                    f"{route_label} · {len(tool_calls)} tool call(s)",
                    expanded=False
                ):
                    for idx, call in enumerate(tool_calls, 1):
                        st.markdown(f"**Tool {idx}: `{call.get('name')}`**")
                        args = call.get("arguments", {})
                        if args:
                            st.json(args)
                        sql = call.get("generated_sql")
                        if sql:
                            st.markdown("**Generated SQL:**")
                            st.code(sql, language="sql")
                        res = call.get("result")
                        if res is not None:
                            with st.expander("Raw tool result", expanded=False):
                                st.json(res)
                        if idx < len(tool_calls):
                            st.divider()

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer,
                "tool_calls": tool_calls,
                "route": route,   # persist so history-replay shows same label
            })

        except Exception as err:
            err_str = str(err)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                display = ("Gemini API quota exceeded. Please wait for your quota to reset "
                           "and try again.")
            elif "API key" in err_str:
                display = "Gemini API key is invalid or not found."
            else:
                display = f"Unable to process question: {err_str[:300]}"

            placeholder.error(display)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": display,
                "tool_calls": [],
            })

st.markdown("---")
st.markdown(
    f'<div style="background:#EFF4FA;border-radius:6px;padding:0.7rem 1rem;'
    f'font-size:0.78rem;color:{MID_GREY};">'
    f'<b>Security note:</b> All SQL queries are validated and executed in read-only mode. '
    f'INSERT, UPDATE, DELETE and schema-modification statements are rejected. '
    f'Results are derived from tool executions, not from model-generated text.</div>',
    unsafe_allow_html=True
)
st.caption(f"PL Capital · AI Analyst · Model: {MODEL_NAME} · Conversation history: {len(st.session_state.chat_history)//2} exchanges")
