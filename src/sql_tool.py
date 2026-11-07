
from database import run_sql_query


FEW_SHOT_EXAMPLES = """
EXAMPLE 1:

Question:
For each portfolio, show the total value of Technology
sector holdings and its percentage of total portfolio value.

Correct SQL:
WITH portfolio_tech_value AS (
    SELECT
        p.portfolio_id,
        p.portfolio_name,
        SUM(h.quantity * s.current_price) AS tech_value
    FROM portfolios p
    JOIN holdings h ON p.portfolio_id = h.portfolio_id
    JOIN securities s ON h.security_id = s.security_id
    JOIN sectors sec ON s.sector_id = sec.sector_id
    WHERE sec.sector_name = 'Technology'
    GROUP BY p.portfolio_id, p.portfolio_name
),
portfolio_total_value AS (
    SELECT
        p.portfolio_id,
        SUM(h.quantity * s.current_price) AS total_value
    FROM portfolios p
    JOIN holdings h ON p.portfolio_id = h.portfolio_id
    JOIN securities s ON h.security_id = s.security_id
    GROUP BY p.portfolio_id
)
SELECT
    ptv.portfolio_name,
    ptv.tech_value,
    ptv2.total_value,
    ROUND(ptv.tech_value * 100.0 / ptv2.total_value, 2)
        AS tech_percentage
FROM portfolio_tech_value ptv
JOIN portfolio_total_value ptv2
    ON ptv.portfolio_id = ptv2.portfolio_id
ORDER BY tech_percentage DESC;


EXAMPLE 2:

Question:
Find portfolios with holdings in more than 5 different
sectors and show their diversification metrics.

Correct SQL:
WITH portfolio_sector_count AS (
    SELECT
        p.portfolio_id,
        p.portfolio_name,
        COUNT(DISTINCT sec.sector_id) AS sector_count
    FROM portfolios p
    JOIN holdings h ON p.portfolio_id = h.portfolio_id
    JOIN securities s ON h.security_id = s.security_id
    JOIN sectors sec ON s.sector_id = sec.sector_id
    WHERE s.asset_type = 'Stock'
    GROUP BY p.portfolio_id, p.portfolio_name
    HAVING COUNT(DISTINCT sec.sector_id) > 5
),
portfolio_holdings_count AS (
    SELECT
        p.portfolio_id,
        COUNT(h.holding_id) AS total_holdings
    FROM portfolios p
    JOIN holdings h ON p.portfolio_id = h.portfolio_id
    GROUP BY p.portfolio_id
)
SELECT
    psc.portfolio_name,
    psc.sector_count,
    phc.total_holdings,
    ROUND(
        CAST(psc.sector_count AS REAL) / phc.total_holdings,
        3
    ) AS diversification_ratio
FROM portfolio_sector_count psc
JOIN portfolio_holdings_count phc
    ON psc.portfolio_id = phc.portfolio_id
ORDER BY diversification_ratio DESC;
"""


def generate_sql(
    user_question,
    client,
    model_name,
    schema_description
):

    prompt = f"""
You are an expert SQLite query generator for a
portfolio analytics system.

DATABASE SCHEMA:
{schema_description}

RULES:
1. Generate only valid SQLite SELECT queries.
2. Never generate INSERT, UPDATE, DELETE, DROP or ALTER.
3. Use only provided tables and columns.
4. Use correct JOIN conditions.
5. Do not invent column names.
6. Return only SQL without Markdown.
7. Use LIMIT for top N questions.
8. Use CTEs for separate aggregations.
9. Count actual holding records using COUNT(holding_id).
10. Count sectors using COUNT(DISTINCT sector_id).
11. For equity exposure, exclude bonds using
    securities.asset_type = 'Stock'.
12. For diversification ratio, calculate
    sector_count / total_holdings.
13. For sector value percentages, calculate sector value
    and total portfolio value separately.
14. Do not include portfolios without the requested sector
    when the question asks for that sector's holdings.

FEW-SHOT EXAMPLES:
{FEW_SHOT_EXAMPLES}

USER QUESTION:
{user_question}

SQL QUERY:
"""

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={"temperature": 0}
    )

    if not response.text:
        raise ValueError("Gemini returned an empty SQL response.")

    sql = response.text.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql


def sql_query_tool(
    user_question,
    client,
    model_name,
    schema_description
):

    try:
        sql = generate_sql(
            user_question,
            client,
            model_name,
            schema_description
        )

        result = run_sql_query(sql)

        return {
            "success": result["success"],
            "question": user_question,
            "generated_sql": sql,
            "result": result
        }

    except Exception as e:
        return {
            "success": False,
            "question": user_question,
            "error": str(e)
        }
