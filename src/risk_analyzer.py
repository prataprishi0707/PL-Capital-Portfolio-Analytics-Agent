
from portfolio_health import analyze_portfolio_health


def analyze_portfolio_risk(portfolio_name):

    # 1. Get portfolio health analysis
    health = analyze_portfolio_health(portfolio_name)

    if not health.get("success"):
        return {
            "success": False,
            "error": health.get("error")
        }

    performance = health["performance"]
    risk = health["risk_metrics"]

    # 2. Extract available risk indicators
    risk_indicators = {
        "beta": {
            "value": risk["beta"] if risk else None,
            "description": "Sensitivity to market movements"
        },
        "var_95": {
            "value": risk["var_95"] if risk else None,
            "description": "95% Value at Risk"
        },
        "var_99": {
            "value": risk["var_99"] if risk else None,
            "description": "99% Value at Risk"
        },
        "cvar_95": {
            "value": risk["cvar_95"] if risk else None,
            "description": "Conditional Value at Risk"
        },
        "volatility": {
            "value": performance["volatility"] if performance else None,
            "description": "Historical portfolio volatility"
        },
        "max_drawdown": {
            "value": performance["max_drawdown"] if performance else None,
            "description": "Maximum observed portfolio drawdown"
        },
        "sharpe_ratio": {
            "value": performance["sharpe_ratio"] if performance else None,
            "description": "Risk-adjusted return"
        },
        "sortino_ratio": {
            "value": risk["sortino_ratio"] if risk else None,
            "description": "Downside-risk-adjusted return"
        },
        "tracking_error": {
            "value": risk["tracking_error"] if risk else None,
            "description": "Deviation from benchmark returns"
        }
    }

    # 3. Separate available and unavailable metrics
    available_metrics = []
    unavailable_metrics = []

    for metric, details in risk_indicators.items():

        if details["value"] is not None:
            available_metrics.append(metric)
        else:
            unavailable_metrics.append(metric)

    # 4. Collect risk observations
    risk_alerts = health["alerts"]

    high_alerts = [
        alert for alert in risk_alerts
        if alert["severity"] == "high"
    ]

    medium_alerts = [
        alert for alert in risk_alerts
        if alert["severity"] == "medium"
    ]

    # 5. Determine observed risk signal level
    if not performance and not risk:
        risk_level = "not_assessed"

    elif high_alerts:
        risk_level = "high"

    elif medium_alerts:
        risk_level = "moderate"

    else:
        risk_level = "lower_observed_signals"

    # 6. Include concentration information
    concentration = health["sector_concentration"]

    # 7. Return risk analysis
    return {
        "success": True,

        "portfolio": health["portfolio"]["portfolio_name"],

        "analysis_status": health["analysis_status"],

        "risk_level": risk_level,

        "risk_indicators": risk_indicators,

        "available_metrics": available_metrics,

        "unavailable_metrics": unavailable_metrics,

        "risk_alerts": risk_alerts,

        "data_quality_alerts": health["data_quality_alerts"],

        "sector_concentration": concentration,

        "total_equity_exposure": health["total_equity_exposure"],

        "data_dates": {
            "performance_date": (
                performance["performance_date"]
                if performance else None
            ),
            "risk_date": (
                risk["calculation_date"]
                if risk else None
            )
        },

        "thresholds_note": health["thresholds_note"],

        "data_note": (
            "Risk analysis uses the latest available historical "
            "dataset records. It is not a live risk assessment "
            "or investment recommendation."
        )
    }
