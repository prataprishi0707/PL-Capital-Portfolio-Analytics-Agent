"""
PL Capital AI Portfolio Analytics Agent.
Provides intelligent orchestrator and function routing utilizing Gemini and deterministic rules.
"""

import json
import sys
from pathlib import Path
from google.genai import types

# Ensure correct imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import run_sql_query
from exposure_calculator import calculate_sector_exposure
from portfolio_health import analyze_portfolio_health
from portfolio_comparison import compare_portfolios
from risk_analyzer import analyze_portfolio_risk
from reconciliation import reconcile_portfolio
from sql_tool import FEW_SHOT_EXAMPLES
from router import route_query


def create_agent_tools():
    return [
        types.Tool(
            function_declarations=[
                # TOOL 1: SQL Query Tool
                types.FunctionDeclaration( 
                    name="run_sql_query",
                    description=(
                        "Execute a validated, read-only SQLite SELECT query. "
                        "Use for general database retrieval, portfolio "
                        "details, holdings, AUM, performance, risk, "
                        "transactions and custom SQL calculations. "
                        "Do not use when a specialized analytical tool "
                        "directly provides the requested result."
                    ),
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "SQLite SELECT query"
                            }
                        },
                        "required": ["query"]
                    }
                ),

                # TOOL 2: Sector Exposure Calculator
                types.FunctionDeclaration(
                    name="calculate_sector_exposure",
                    description=(
                        "Calculate sector-wise equity exposure for a named portfolio. "
                        "Use this tool whenever the user asks for sector "
                        "exposure, sector-wise allocation, or an exposure "
                        "breakdown for a portfolio. Do not use general SQL "
                        "for this task. Bonds are excluded. Resolve a "
                        "clearly identifiable shortened portfolio name "
                        "to its canonical database name; ask if ambiguous."
                    ),
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "portfolio_name": {
                                "type": "STRING",
                                "description": "Portfolio name"
                            }
                        },
                        "required": ["portfolio_name"]
                    }
                ),

                # TOOL 3: Portfolio Health Analyzer
                types.FunctionDeclaration(
                    name="analyze_portfolio_health",
                    description=(
                        "Analyze the overall health of a portfolio. "
                        "Returns performance metrics, risk metrics, "
                        "asset allocation, sector concentration, alerts and warnings. "
                        "Use for comprehensive portfolio analysis."
                    ),
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "portfolio_name": {
                                "type": "STRING",
                                "description": "Portfolio name"
                            }
                        },
                        "required": ["portfolio_name"]
                    }
                ),

                # TOOL 4: Portfolio Comparison
                types.FunctionDeclaration(
                    name="compare_portfolios",
                    description=(
                        "Compare two different portfolios using "
                        "performance, risk metrics, asset allocation, "
                        "sector exposure and concentration. "
                        "Missing metrics are reported as unavailable. "
                        "Use whenever the user asks to compare portfolios."
                    ),
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "portfolio_name_1": {
                                "type": "STRING",
                                "description": "First portfolio name"
                            },
                            "portfolio_name_2": {
                                "type": "STRING",
                                "description": "Second portfolio name"
                            }
                        },
                        "required": [
                            "portfolio_name_1",
                            "portfolio_name_2"
                        ]
                    }
                ),

                # TOOL 5: Portfolio Risk Analyzer
                types.FunctionDeclaration(
                    name="analyze_portfolio_risk",
                    description=(
                        "Perform focused portfolio risk analysis. "
                        "Returns beta, VaR, CVaR, volatility, "
                        "maximum drawdown, Sharpe ratio, Sortino ratio, "
                        "risk alerts and data availability. "
                        "Use for risk assessment and risk-related questions."
                    ),
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "portfolio_name": {
                                "type": "STRING",
                                "description": "Portfolio name"
                            }
                        },
                        "required": ["portfolio_name"]
                    }
                ),

                # TOOL 6: Portfolio Reconciliation
                types.FunctionDeclaration(
                    name="reconcile_portfolio",
                    description=(
                        "Reconcile recorded holding weights against "
                        "market-value-computed weights. "
                        "Detects weight drift, duplicate securities, "
                        "zero-weight holdings and total allocation gaps. "
                        "Use when the user asks about reconciliation, "
                        "weight drift, holdings check or data integrity."
                    ),
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "portfolio_name": {
                                "type": "STRING",
                                "description": "Portfolio name"
                            }
                        },
                        "required": ["portfolio_name"]
                    }
                )
            ]
        )
    ]


def ask_portfolio_agent(
    user_question,
    client,
    model_name,
    schema_description,
    return_details=False,
    conversation_history=None
):
    # 1. Deterministic offline routing first
    routing = route_query(user_question)
    if routing.confidence == 1.0 and routing.tool_name:
        # Execute matching tool offline
        result = None
        if routing.tool_name == "run_sql_query":
            result = run_sql_query(**routing.arguments)
        elif routing.tool_name == "calculate_sector_exposure":
            result = calculate_sector_exposure(**routing.arguments)
        elif routing.tool_name == "analyze_portfolio_health":
            result = analyze_portfolio_health(**routing.arguments)
        elif routing.tool_name == "compare_portfolios":
            result = compare_portfolios(**routing.arguments)
        elif routing.tool_name == "analyze_portfolio_risk":
            result = analyze_portfolio_risk(**routing.arguments)
        elif routing.tool_name == "reconcile_portfolio":
            result = reconcile_portfolio(**routing.arguments)

        # Prepare simplified structured explanation
        if routing.tool_name == "run_sql_query" and result.get("success"):
            rows = result.get("rows", [])
            if len(rows) == 1 and len(rows[0]) == 1:
                val = list(rows[0].values())[0]
                answer = f"Based on database analysis, the result is: {val}"
            else:
                answer = f"Successfully fetched {len(rows)} rows from the database. Here is the query result: {json.dumps(rows[:5])}"
        else:
            answer = f"Successfully executed {routing.tool_name} to fulfill your request. Result: {json.dumps(result)}"

        if return_details:
            return {
                "answer": answer,
                "tool_calls": [{
                    "name": routing.tool_name,
                    "arguments": routing.arguments,
                    "generated_sql": routing.arguments.get("query") if routing.tool_name == "run_sql_query" else None,
                    "result": result
                }]
            }
        return answer

    # 2. Fallback to Gemini LLM orchestrator
    system_prompt = f"""
You are an AI Portfolio Analytics Agent.

Your job is to answer portfolio-related questions using
the appropriate available analytical tools.

DATABASE SCHEMA:
{schema_description}

SQL GENERATION GUIDANCE:
{FEW_SHOT_EXAMPLES}

TOOL SELECTION RULES:

1. calculate_sector_exposure:
   Preferred for sector-wise equity exposure, sector allocation,
   or exposure breakdown for a named portfolio.
   Use it instead of SQL for these questions.
   Resolve an obvious shortened portfolio label to its exact
   canonical database name. Ask if the portfolio is ambiguous.

2. analyze_portfolio_health:
   Use for complete portfolio health analysis, including
   performance, risk metrics, asset allocation and concentration.

3. compare_portfolios:
   Use when the user asks to compare two portfolios.
   Both portfolio names must be identifiable.

4. analyze_portfolio_risk:
   Use for focused risk analysis involving beta, VaR, CVaR,
   volatility, drawdown, Sharpe ratio and risk alerts.

5. run_sql_query:
   Use for general database retrieval and calculations such as
   portfolio lists, AUM, holdings, transactions and custom SQL
   questions not directly covered by a specialized tool.

6. reconcile_portfolio:
   Use when the user asks about reconciliation, weight drift,
   holdings data integrity, or wants to check whether recorded
   weights match market-value-computed weights.

TOOL-CALL EFFICIENCY:

- Choose the single most relevant tool that can answer the question.
- Do not make multiple calls to the same tool just to explore
  additional information that was not requested.
- If one tool call provides the requested information, stop
  calling tools and formulate the answer.
- Use multiple tools only when the question genuinely requires
  information that no single tool can provide.
- Do not call SQL to verify or repeat a result already returned
  by the appropriate specialized tool.

SQL RESPONSE REQUIREMENTS:

- Generate valid SQLite SELECT queries only.
- Use the supplied database schema. Never invent tables or columns.
- Select only the columns explicitly requested or necessary
  to answer the question.
- Do not add unrelated IDs, status fields or raw columns.
- Follow requested filters, sorting, grouping and top-N limits.
- Use correct JOIN conditions and aggregation logic.

IMPORTANT INSTRUCTIONS:

- Use conversation history to resolve references such as
  "it", "its", "that portfolio" and "the other one".
- Preserve portfolio names and relevant context established earlier.
- If a follow-up is ambiguous, ask for clarification instead of guessing.
- Never treat an earlier tool result as current live market data.
- Never invent portfolio names or numerical results.
- Base your final answer strictly on tool results.
- Clearly mention missing or unavailable data.
- Distinguish a genuine zero value from unavailable or missing data.
- Do not describe historical dataset values as live market data.
- Do not make unsupported investment recommendations.
- Explain important findings in simple, professional language.
- If a tool returns an error, communicate it honestly.
"""

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.0,
        tools=create_agent_tools(),
    )

    # Restore recent conversation context
    contents = []
    if conversation_history:
        recent_history = conversation_history[-6:]
        for message in recent_history:
            role = message.get("role")
            message_text = str(message.get("content", "")).strip()
            if role not in ("user", "assistant") or not message_text:
                continue
            contents.append(
                types.Content(
                    role="model" if role == "assistant" else "user",
                    parts=[
                        types.Part.from_text(text=message_text[:2000])
                    ]
                )
            )

    # Gemini conversation history must begin with a user message.
    while contents and contents[0].role == "model":
        contents.pop(0)

    # Append current question
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=user_question)
            ]
        )
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )
    except Exception as error:
        answer = f"LLM orchestration call failed. API error: {error}"
        if return_details:
            return {"answer": answer, "tool_calls": []}
        return answer

    tool_history = []

    for _ in range(4):
        if not response.function_calls:
            break

        function_response_parts = []

        for call in response.function_calls:
            arguments = {}
            if call.args:
                # Convert map to dict safely
                arguments = dict(call.args)

            result = None
            query = None

            if call.name == "run_sql_query":
                query = arguments.get("query")
                result = run_sql_query(query)
            elif call.name == "calculate_sector_exposure":
                result = calculate_sector_exposure(
                    arguments.get("portfolio_name")
                )
            elif call.name == "analyze_portfolio_health":
                result = analyze_portfolio_health(
                    arguments.get("portfolio_name")
                )
            elif call.name == "compare_portfolios":
                result = compare_portfolios(
                    arguments.get("portfolio_name_1"),
                    arguments.get("portfolio_name_2")
                )
            elif call.name == "analyze_portfolio_risk":
                result = analyze_portfolio_risk(
                    arguments.get("portfolio_name")
                )
            elif call.name == "reconcile_portfolio":
                result = reconcile_portfolio(
                    arguments.get("portfolio_name")
                )

            # Ensure complete JSON serialization safety
            result = json.loads(
                json.dumps(
                    result,
                    default=lambda x: (
                        x.item() if hasattr(x, "item") else str(x)
                    )
                )
            )

            tool_history.append({
                "name": call.name,
                "arguments": arguments,
                "generated_sql": query,
                "result": result
            })

            function_response_parts.append(
                types.Part.from_function_response(
                    name=call.name,
                    response={"result": result}
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=function_response_parts
            )
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        except Exception as error:
            answer = f"The tool executed, but Gemini could not generate the final response. API error: {error}"
            if return_details:
                return {"answer": answer, "tool_calls": tool_history}
            return answer

    answer = response.text if response.text else "I have compiled the requested portfolio intelligence results."
    if return_details:
        return {
            "answer": answer,
            "tool_calls": tool_history
        }
    return answer
