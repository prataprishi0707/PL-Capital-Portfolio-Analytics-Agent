"""
PL Capital Risk Intelligence (v2 — consistency-preserving).

Design principle: a high risk SIGNAL can never be hidden by a high risk SCORE.

Outputs distinguish three independent things:
    risk_level   — observed risk SIGNAL level, derived from alerts.
                   This is authoritative for the headline.
    risk_score   — numeric aggregate (0-100, lower = more risk) based on the
                   metric values that are actually present.
    risk_tier    — categorical interpretation of the score, BUT capped by the
                   observed signal level. A "high" signal caps the tier at
                   "aggressive"; a "moderate" signal caps it at "moderate".

Missing metrics reduce CONFIDENCE in the assessment; they never imply safety.
data_completeness reports what fraction of the nine indicators are present.

All formulas and thresholds are documented inline and in *_note fields.
No risk data is fabricated; unavailable metrics stay None.
"""

import math
from portfolio_health import analyze_portfolio_health


def _is_valid_number(v):
    """True only for finite real numbers (not None, NaN, inf, bool, or strings).
    Only accepts int/float types that are finite — a string is treated as
    invalid because risk metrics from the DB are stored as REAL/INTEGER,
    so a string would be unexpected data, not a value to coerce.
    Huge integers (e.g. 10**400) that OverflowError on float() conversion are
    treated as invalid."""
    if v is None or isinstance(v, bool) or isinstance(v, str):
        return False
    if not isinstance(v, (int, float)):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return False
    return not (math.isnan(f) or math.isinf(f))


# Total number of distinct risk indicators reported.
TOTAL_RISK_INDICATORS = 9


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

    # 2. Extract available risk indicators (None stays None; never fabricated).
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

    # Sanitise: replace any non-finite stored values with None so they cannot
    # silently enter the score computation.
    for key, details in risk_indicators.items():
        if not _is_valid_number(details["value"]):
            details["value"] = None
            details["data_issue"] = "non_finite_or_missing"
        else:
            details["value"] = float(details["value"])

    # 3. Separate available and unavailable metrics.
    available_metrics = [m for m, d in risk_indicators.items() if d["value"] is not None]
    unavailable_metrics = [m for m, d in risk_indicators.items() if d["value"] is None]

    # 4. Collect risk alerts (the SIGNAL).
    risk_alerts = health["alerts"]
    high_alerts = [a for a in risk_alerts if a.get("severity") == "high"]
    medium_alerts = [a for a in risk_alerts if a.get("severity") == "medium"]

    # 5. Observed risk SIGNAL level (authoritative headline).
    #    Derived from alerts, NOT from the score, so it cannot be hidden.
    if not performance and not risk:
        signal_level = "not_assessed"
    elif high_alerts:
        signal_level = "high"
    elif medium_alerts:
        signal_level = "moderate"
    else:
        signal_level = "lower_observed_signals"

    # 6. Risk SCORE (numeric aggregate; only valid metrics contribute).
    #    Missing metrics do NOT add points back. The score is only meaningful
    #    when read together with data_completeness.
    risk_score = 100

    beta_val = risk_indicators["beta"]["value"]
    var95_val = risk_indicators["var_95"]["value"]
    vol_val = risk_indicators["volatility"]["value"]
    drawdown_val = risk_indicators["max_drawdown"]["value"]

    if beta_val is not None:
        if beta_val > 1.5:
            risk_score -= 20
        elif beta_val > 1.2:
            risk_score -= 10

    if var95_val is not None:
        if var95_val < -8:
            risk_score -= 20
        elif var95_val < -5:
            risk_score -= 10

    if vol_val is not None:
        if vol_val > 25:
            risk_score -= 15
        elif vol_val > 18:
            risk_score -= 8

    if drawdown_val is not None:
        if drawdown_val < -20:
            risk_score -= 15
        elif drawdown_val < -10:
            risk_score -= 8

    if not performance and not risk:
        risk_score -= 20
    elif not performance or not risk:
        risk_score -= 10

    risk_score = max(0, min(100, risk_score))

    # 7. Score-derived tier BEFORE capping by the signal.
    if risk_score >= 70:
        score_tier = "conservative"
    elif risk_score >= 40:
        score_tier = "moderate"
    else:
        score_tier = "aggressive"

    # 8. Final risk_tier — capped by the authoritative signal level.
    #    A high signal can NEVER be overridden by a high score.
    if signal_level == "high":
        risk_tier = "aggressive"
    elif signal_level == "moderate":
        risk_tier = "moderate" if score_tier != "aggressive" else "aggressive"
    elif signal_level == "not_assessed":
        risk_tier = "not_assessed"
    else:
        # signal_level == "lower_observed_signals"
        risk_tier = score_tier

    # 9. Data completeness + assessment confidence.
    data_completeness_pct = round(
        len(available_metrics) / TOTAL_RISK_INDICATORS * 100, 2
    )

    if data_completeness_pct >= 90:
        assessment_confidence = "high"
    elif data_completeness_pct >= 50:
        assessment_confidence = "medium"
    else:
        assessment_confidence = "low"

    # 10. Consistency explanation: make the relationship explicit and auditable.
    consistency_note = (
        f"signal_level='{signal_level}' is derived from risk alerts and is the "
        f"authoritative headline. risk_score={risk_score} is a numeric aggregate "
        f"of present metrics only. risk_tier='{risk_tier}' is the score-derived "
        f"tier ('{score_tier}') CAPPED by the signal level, so a high signal can "
        f"never be hidden by a high score. data_completeness={data_completeness_pct}% "
        f"({len(available_metrics)}/{TOTAL_RISK_INDICATORS} indicators present) "
        f"sets assessment_confidence='{assessment_confidence}'."
    )

    # 11. Include concentration information.
    concentration = health["sector_concentration"]

    return {
        "success": True,
        "portfolio": health["portfolio"]["portfolio_name"],
        "analysis_status": health["analysis_status"],

        # Headline (authoritative signal).
        "risk_level": signal_level,

        # Numeric score and its interpretation.
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "score_tier_uncapped": score_tier,
        "risk_score_note": (
            "risk_score starts at 100 (lower = more risk). Deductions: "
            "beta>1.5 -20, beta>1.2 -10; VaR95<-8% -20, VaR95<-5% -10; "
            "volatility>25% -15, >18% -8; drawdown<-20% -15, <-10% -8; "
            "missing data -10 to -20. Floor: 0, ceiling: 100. "
            "Missing metrics reduce CONFIDENCE, they never imply safety."
        ),

        # Data completeness + confidence.
        "data_completeness_pct": data_completeness_pct,
        "available_metric_count": len(available_metrics),
        "total_indicators": TOTAL_RISK_INDICATORS,
        "assessment_confidence": assessment_confidence,
        "consistency_note": consistency_note,

        # Metric detail.
        "risk_indicators": risk_indicators,
        "available_metrics": available_metrics,
        "unavailable_metrics": unavailable_metrics,
        "risk_alerts": risk_alerts,
        "high_alert_count": len(high_alerts),
        "medium_alert_count": len(medium_alerts),

        "data_quality_alerts": health["data_quality_alerts"],
        "sector_concentration": concentration,
        "total_equity_exposure": health["total_equity_exposure"],

        "data_dates": {
            "performance_date": (
                performance["performance_date"] if performance else None
            ),
            "risk_date": (
                risk["calculation_date"] if risk else None
            ),
        },

        "thresholds_note": health["thresholds_note"],
        "data_note": (
            "Risk analysis uses the latest available historical dataset "
            "records. It is not a live risk assessment or investment "
            "recommendation. No risk data is fabricated; unavailable "
            "metrics are reported as None."
        ),
    }
