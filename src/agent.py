
import json
from google.genai import types

from database import run_sql_query
from exposure_calculator import calculate_sector_exposure
from portfolio_health import analyze_portfolio_health
from portfolio_comparison import compare_portfolios
from risk_analyzer import analyze_portfolio_risk
from sql_tool import FEW_SHOT_EXAMPLES


def create_agent_tools():

    return [
        types.Tool(
            function_declarations=[

                # TOOL 1: SQL Query Tool
                types.FunctionDeclaration(
                    name="run_sql_query",
                    description=(
                        "Execute a validated, read-only SQLite SELECT "
                        "query. Use for portfolio details, holdings, "
                        "AUM, performance, risk and transactions."
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

                # TOOL 2: Exposure Calculator
                types.FunctionDeclaration(
                    name="calculate_sector_exposure",
                    description=(
                        "Calculate sector-wise equity exposure for a "
                        "portfolio. Bonds are excluded. Use for sector "
                        "exposure and allocation questions."
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
                        "asset allocation, sector concentration, "
                        "risk alerts and data quality warnings. "
                        "Use when asked whether a portfolio is healthy "
                        "or for a complete portfolio health analysis."
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

                # TOOL 4: Portfolio Comparison Engine
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

                # TOOL 5: Risk Intelligence
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
                )
            ]
        )
    ]


def ask_portfolio_agent(
    user_question,
    client,
    model_name,
    schema_description,
    return_details=False
):

    system_prompt = f"""
You are an AI Portfolio Analytics Agent.

Your job is to answer portfolio-related questions using
the appropriate available analytical tools.

DATABASE SCHEMA:
{schema_description}

SQL GENERATION GUIDANCE:
{FEW_SHOT_EXAMPLES}

TOOL SELECTION RULES:

1. run_sql_query:
   Use for general database questions such as portfolio details,
   AUM, holdings, transactions and specific SQL-based calculations.

2. calculate_sector_exposure:
   Use for sector-wise equity exposure questions.
   Bonds must be excluded.

3. analyze_portfolio_health:
   Use for complete portfolio health analysis, including
   performance, risk metrics, allocation and concentration.

4. compare_portfolios:
   Use when the user asks to compare two portfolios.
   Both portfolio names must be provided.

5. analyze_portfolio_risk:
   Use for focused risk analysis involving beta, VaR, CVaR,
   volatility, drawdown and risk alerts.

IMPORTANT INSTRUCTIONS:

- Choose the most relevant tool for the question.
- Do not use SQL when a specialized analytical tool
  already provides the required result.
- Generate valid SQLite SELECT queries only.
- Use the supplied database schema. Never invent columns.
- Never invent portfolio names or numerical results.
- Base your final answer strictly on tool results.
- Clearly mention missing or unavailable data.
- Never treat missing values as zero.
- Do not describe historical dataset values as live market data.
- Do not make unsupported investment recommendations.
- Explain important findings in simple, professional language.
- If a tool returns an error, communicate it honestly.
"""

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=user_question)
            ]
        )
    ]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=create_agent_tools(),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="AUTO"
            )
        ),
        temperature=0
    )

    tool_history = []

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config
    )

    # Allow multiple tool-calling rounds
    for _ in range(4):

        function_calls = response.function_calls

        if not function_calls:

            answer = response.text or "I couldn't generate an answer."

            if return_details:
                return {
                    "answer": answer,
                    "tool_calls": tool_history
                }

            return answer

        contents.append(response.candidates[0].content)

        function_response_parts = []

        for call in function_calls:

            arguments = dict(call.args)

            # TOOL 1: SQL Query Tool
            if call.name == "run_sql_query":

                query = arguments["query"]
                result = run_sql_query(query)

            # TOOL 2: Exposure Calculator
            elif call.name == "calculate_sector_exposure":

                query = None

                result = calculate_sector_exposure(
                    arguments["portfolio_name"]
                )

            # TOOL 3: Portfolio Health Analyzer
            elif call.name == "analyze_portfolio_health":

                query = None

                result = analyze_portfolio_health(
                    arguments["portfolio_name"]
                )

            # TOOL 4: Portfolio Comparison Engine
            elif call.name == "compare_portfolios":

                query = None

                result = compare_portfolios(
                    arguments["portfolio_name_1"],
                    arguments["portfolio_name_2"]
                )

            # TOOL 5: Risk Intelligence
            elif call.name == "analyze_portfolio_risk":

                query = None

                result = analyze_portfolio_risk(
                    arguments["portfolio_name"]
                )

            else:

                query = None

                result = {
                    "success": False,
                    "error": "Unknown tool requested."
                }

            # Convert results into JSON-compatible values
            result = json.loads(
                json.dumps(
                    result,
                    default=lambda x: (
                        x.item() if hasattr(x, "item") else str(x)
                    )
                )
            )

            # Record actual tool execution
            tool_history.append({
                "name": call.name,
                "arguments": arguments,
                "generated_sql": query,
                "result": result
            })

            # Send tool result back to Gemini
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
            answer = (
                "The tool executed, but Gemini could not generate "
                f"the final response. API error: {error}"
            )

            if return_details:
                return {
                    "answer": answer,
                    "tool_calls": tool_history
                }

            return answer

    answer = (
        "Tool-call limit reached. "
        "Please simplify your question."
    )

    if return_details:
        return {
            "answer": answer,
            "tool_calls": tool_history
        }

    return answer
