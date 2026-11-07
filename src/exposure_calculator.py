
import pandas as pd
from database import get_connection


def calculate_sector_exposure(portfolio_name):

    conn = get_connection()

    try:
        portfolio_query = """
        SELECT portfolio_id, portfolio_name
        FROM portfolios
        WHERE LOWER(TRIM(portfolio_name)) =
              LOWER(TRIM(?))
        """

        portfolio = pd.read_sql_query(
            portfolio_query,
            conn,
            params=(portfolio_name,)
        )

        if portfolio.empty:
            return {
                "success": False,
                "error": f"Portfolio '{portfolio_name}' not found."
            }

        portfolio_id = int(portfolio.iloc[0]["portfolio_id"])

        query = """
        SELECT
            sec.sector_name,
            SUM(h.current_weight) AS total_weight
        FROM holdings h
        JOIN securities s
            ON h.security_id = s.security_id
        JOIN sectors sec
            ON s.sector_id = sec.sector_id
        WHERE h.portfolio_id = ?
          AND s.asset_type = 'Stock'
        GROUP BY sec.sector_id, sec.sector_name
        ORDER BY total_weight DESC
        """

        exposure = pd.read_sql_query(
            query,
            conn,
            params=(portfolio_id,)
        )

        exposure["exposure_percentage"] = (
            exposure["total_weight"] * 100
        ).round(2)

        return {
            "success": True,
            "portfolio_name": portfolio.iloc[0]["portfolio_name"],
            "sector_exposures": exposure[
                ["sector_name", "exposure_percentage"]
            ].to_dict(orient="records"),
            "total_equity_exposure": float(round(
                exposure["total_weight"].sum() * 100, 2
            ))
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        conn.close()
