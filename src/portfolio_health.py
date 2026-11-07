
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "portfolio_database.db"


def analyze_portfolio_health(portfolio_name):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 1. Find portfolio
        portfolio = conn.execute("""
            SELECT *
            FROM portfolios
            WHERE LOWER(portfolio_name) = LOWER(?)
        """, (portfolio_name,)).fetchone()

        if portfolio is None:
            return {
                "success": False,
                "error": f"Portfolio '{portfolio_name}' not found."
            }

        portfolio = dict(portfolio)
        portfolio_id = portfolio["portfolio_id"]

        # 2. Get latest performance metrics
        performance = conn.execute("""
            SELECT *
            FROM portfolio_performance
            WHERE portfolio_id = ?
            ORDER BY performance_date DESC
            LIMIT 1
        """, (portfolio_id,)).fetchone()

        # 3. Get latest risk metrics
        risk = conn.execute("""
            SELECT *
            FROM risk_metrics
            WHERE portfolio_id = ?
            ORDER BY calculation_date DESC
            LIMIT 1
        """, (portfolio_id,)).fetchone()

        performance = dict(performance) if performance else None
        risk = dict(risk) if risk else None

        # 4. Calculate asset allocation
        allocation_rows = conn.execute("""
            SELECT
                s.asset_type,
                COUNT(h.holding_id) AS holding_count,
                ROUND(SUM(h.current_weight) * 100, 2)
                    AS allocation_percentage
            FROM holdings h
            JOIN securities s
                ON h.security_id = s.security_id
            WHERE h.portfolio_id = ?
            GROUP BY s.asset_type
            ORDER BY s.asset_type
        """, (portfolio_id,)).fetchall()

        allocation = [dict(row) for row in allocation_rows]

        # 5. Calculate total recorded asset allocation
        total_stock_allocation = round(
            sum(
                row["allocation_percentage"] or 0
                for row in allocation
                if str(row["asset_type"]).lower() == "stock"
            ),
            2
        )

        total_bond_allocation = round(
            sum(
                row["allocation_percentage"] or 0
                for row in allocation
                if str(row["asset_type"]).lower() == "bond"
            ),
            2
        )

        total_recorded_allocation = round(
            sum(
                row["allocation_percentage"] or 0
                for row in allocation
            ),
            2
        )

        unallocated_allocation = round(
            100 - total_recorded_allocation,
            2
        )

        unallocated_equity_exposure = unallocated_allocation

        # 6. Calculate sector exposure (stocks only)
        sector_rows = conn.execute("""
            SELECT
                sec.sector_name,
                COUNT(h.holding_id) AS holding_count,
                ROUND(SUM(h.current_weight) * 100, 2)
                    AS exposure_percentage
            FROM holdings h
            JOIN securities s
                ON h.security_id = s.security_id
            LEFT JOIN sectors sec
                ON s.sector_id = sec.sector_id
            WHERE h.portfolio_id = ?
              AND LOWER(s.asset_type) = 'stock'
            GROUP BY sec.sector_name
            ORDER BY exposure_percentage DESC
        """, (portfolio_id,)).fetchall()

        all_sector_exposures = [dict(row) for row in sector_rows]

        missing_sector_exposure = round(
            sum(
                row["exposure_percentage"] or 0
                for row in all_sector_exposures
                if row["sector_name"] is None
            ),
            2
        )

        sector_exposures = [
            row for row in all_sector_exposures
            if row["sector_name"] is not None
        ]

        total_equity_exposure = round(
            sum(
                row["exposure_percentage"] or 0
                for row in sector_exposures
            ),
            2
        )

        # 7. Calculate sector concentration
        if total_equity_exposure > 0:
            sector_shares = [
                row["exposure_percentage"] / total_equity_exposure
                for row in sector_exposures
            ]
            hhi = sum(share ** 2 for share in sector_shares)
            effective_sectors = 1 / hhi if hhi else None
            largest_sector = sector_exposures[0]
        else:
            hhi = None
            effective_sectors = None
            largest_sector = None

        # 8. Generate portfolio risk alerts
        alerts = []

        if largest_sector and total_equity_exposure > 0:
            largest_sector_share = (
                largest_sector["exposure_percentage"]
                / total_equity_exposure * 100
            )
            if largest_sector_share >= 40:
                alerts.append({
                    "type": "sector_concentration",
                    "severity": "high",
                    "message": f"{largest_sector['sector_name']} represents {largest_sector_share:.1f}% of equity exposure."
                })

        if risk:
            if risk["beta"] is not None and risk["beta"] > 1.2:
                alerts.append({
                    "type": "market_sensitivity",
                    "severity": "high",
                    "message": f"Portfolio beta is {risk['beta']}, indicating higher sensitivity to market movements."
                })
            if risk["var_95"] is not None and risk["var_95"] <= -5:
                alerts.append({
                    "type": "value_at_risk",
                    "severity": "high",
                    "message": f"95% VaR is {risk['var_95']}."
                })

        if performance:
            if performance["volatility"] is not None and performance["volatility"] > 20:
                alerts.append({
                    "type": "volatility",
                    "severity": "high",
                    "message": f"Portfolio volatility is {performance['volatility']}."
                })
            if performance["max_drawdown"] is not None and performance["max_drawdown"] <= -10:
                alerts.append({
                    "type": "drawdown",
                    "severity": "high",
                    "message": f"Maximum drawdown is {performance['max_drawdown']}%."
                })
            if performance["sharpe_ratio"] is not None and performance["sharpe_ratio"] < 1:
                alerts.append({
                    "type": "risk_adjusted_return",
                    "severity": "medium",
                    "message": f"Sharpe ratio is {performance['sharpe_ratio']}."
                })

        # 9. Generate data-quality alerts separately
        data_quality_alerts = []

        if abs(unallocated_allocation) > 0.01:
            if unallocated_allocation > 0:
                alert_type = "allocation_gap"
                message = f"{unallocated_allocation}% of total portfolio allocation is not represented in the recorded holdings."
            else:
                alert_type = "allocation_overage"
                message = f"Recorded asset allocation exceeds 100% by {abs(unallocated_allocation)}%."

            data_quality_alerts.append({
                "type": alert_type,
                "severity": "warning",
                "message": message
            })

        if missing_sector_exposure > 0.01:
            data_quality_alerts.append({
                "type": "missing_sector_mapping",
                "severity": "warning",
                "message": f"{missing_sector_exposure}% of equity exposure has no valid sector mapping."
            })

        if performance and risk:
            analysis_status = "full"
        elif performance or risk:
            analysis_status = "partial"
        else:
            analysis_status = "holdings_only"

        return {
            "success": True,
            "portfolio": portfolio,
            "analysis_status": analysis_status,
            "performance": performance,
            "risk_metrics": risk,
            "asset_allocation": allocation,
            "total_stock_allocation": total_stock_allocation,
            "total_bond_allocation": total_bond_allocation,
            "total_recorded_allocation": total_recorded_allocation,
            "unallocated_allocation": unallocated_allocation,
            "unallocated_equity_exposure": unallocated_equity_exposure,
            "missing_sector_exposure": missing_sector_exposure,
            "sector_exposures": sector_exposures,
            "total_equity_exposure": total_equity_exposure,
            "sector_concentration": {
                "hhi": round(hhi, 4) if hhi is not None else None,
                "effective_number_of_sectors": round(effective_sectors, 2) if effective_sectors is not None else None,
                "largest_sector": largest_sector
            },
            "alerts": alerts,
            "data_quality_alerts": data_quality_alerts,
            "thresholds_note": "Alerts use illustrative internal thresholds, not official PL Capital risk limits.",
            "data_note": "Performance and risk metrics reflect the latest available dataset records, not live market data."
        }
    except sqlite3.Error as error:
        return {
            "success": False,
            "error": str(error)
        }
    finally:
        conn.close()
