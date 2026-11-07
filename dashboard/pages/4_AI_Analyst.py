
import os
import sys
import json
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"

sys.path.insert(0, str(SRC_DIR))

from google import genai
from agent import ask_portfolio_agent
from main import get_schema_description


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Analyst | PL Capital",
    page_icon="🤖",
    layout="wide"
)

st.title("AI Portfolio Analyst")

st.caption(
    "Ask questions about portfolio performance, risk, "
    "sector exposure and investment data."
)


# --------------------------------------------------
# API CONFIGURATION
# --------------------------------------------------

def get_api_key():

    # First check environment variable
    api_key = os.getenv("GOOGLE_API_KEY")

    if api_key:
        return api_key

    # Then try Colab Secrets
    try:
        from google.colab import userdata
        return userdata.get("PlCapitals")

    except Exception:
        return None


def get_gemini_client():

    api_key = get_api_key()

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash"
)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.subheader("AI Analyst")

    st.caption("PL Capital Portfolio Analytics Agent")

    st.divider()

    st.markdown("**Available capabilities**")

    st.write("1. SQL Query Tool")
    st.write("2. Sector Exposure Calculator")
    st.write("3. Portfolio Health Analyzer")
    st.write("4. Portfolio Comparison")
    st.write("5. Risk Intelligence")

    st.divider()

    st.markdown("**Example questions**")

    examples = [
        "Which portfolio has the highest one-year return?",
        "Calculate sector exposure for Tech Innovation Fund.",
        "Compare Tech Innovation Fund and Growth Equity Fund.",
        "What are the major risks in Tech Innovation Fund?",
        "Show the total AUM of all portfolios."
    ]

    for example in examples:
        st.caption("• " + example)

    st.divider()

    if st.button("Clear Conversation", width="stretch"):
        st.session_state.chat_history = []
        st.rerun()

    st.caption(f"Model: {MODEL_NAME}")

# --------------------------------------------------
# WELCOME SECTION
# --------------------------------------------------

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if not st.session_state.chat_history:

    st.info(
        "Welcome to PL Capital AI Analyst. "
        "Select a question below or type your own."
    )

    st.subheader("Try asking")

    for index, example in enumerate(examples):

        if st.button(
            example,
            key=f"suggestion_{index}",
            width="stretch"
        ):
            st.session_state.pending_question = example
            st.rerun()



# --------------------------------------------------
# DISPLAY CHAT HISTORY
# --------------------------------------------------

for message in st.session_state.chat_history:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])

        # Display tool execution details
        if message["role"] == "assistant":

            tool_calls = message.get("tool_calls", [])

            if tool_calls:

                with st.expander(
                    f"View {len(tool_calls)} tool execution(s)"
                ):

                    for index, call in enumerate(tool_calls, 1):

                        st.markdown(
                            f"**Tool {index}: {call.get('name')}**"
                        )

                        st.markdown("Arguments")

                        st.json(call.get("arguments", {}))

                        generated_sql = call.get("generated_sql")

                        if generated_sql:
                            st.markdown("Generated SQL")
                            st.code(generated_sql, language="sql")

                        st.markdown("Tool Result")

                        st.json(call.get("result", {}))

                        if index < len(tool_calls):
                            st.divider()


# --------------------------------------------------
# CHAT INPUT
# --------------------------------------------------

user_question = st.chat_input(
    "Ask your portfolio question..."
)

if st.session_state.pending_question:
    user_question = st.session_state.pending_question
    st.session_state.pending_question = None


# --------------------------------------------------
# PROCESS USER QUESTION
# --------------------------------------------------

if user_question:

    # Display user message
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_question
    })

    with st.chat_message("user"):
        st.markdown(user_question)

    # Generate AI response
    with st.chat_message("assistant"):

        try:

            client = get_gemini_client()

            if client is None:

                raise ValueError(
                    "Gemini API key not found. "
                    "Check your Colab Secret named PlCapitals."
                )

            with st.spinner(
                "Analyzing your question and selecting the appropriate tool..."
            ):

                schema_description = get_schema_description()

                response = ask_portfolio_agent(
                    user_question=user_question,
                    client=client,
                    model_name=MODEL_NAME,
                    schema_description=schema_description,
                    return_details=True
                )

            answer = response.get(
                "answer",
                "No answer was generated."
            )

            tool_calls = response.get("tool_calls", [])

            st.markdown(answer)

            # Show selected tools
            if tool_calls:

                with st.expander(
                    f"View {len(tool_calls)} tool execution(s)"
                ):

                    for index, call in enumerate(tool_calls, 1):

                        st.markdown(
                            f"**Tool {index}: {call.get('name')}**"
                        )

                        st.markdown("Arguments")

                        st.json(call.get("arguments", {}))

                        generated_sql = call.get("generated_sql")

                        if generated_sql:
                            st.markdown("Generated SQL")
                            st.code(generated_sql, language="sql")

                        st.markdown("Tool Result")

                        st.json(call.get("result", {}))

                        if index < len(tool_calls):
                            st.divider()

            # Save assistant response
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer,
                "tool_calls": tool_calls
            })

        except Exception as error:

            error_message = str(error)

            if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:

                display_message = (
                    "Gemini API quota has been exceeded. "
                    "The AI Analyst interface is working, but "
                    "the AI service is temporarily unavailable. "
                    "Please try again when your quota resets."
                )

            elif "API key" in error_message:

                display_message = (
                    "Gemini API key is unavailable. "
                    "Check that the Colab Secret is named PlCapitals."
                )

            else:

                display_message = (
                    f"Unable to process your question: {error_message}"
                )

            st.error(display_message)

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": display_message,
                "tool_calls": []
            })
