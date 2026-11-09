
import math

from portfolio_health import analyze_portfolio_health


# --------------------------------------------------------------------------- #
# Configurable winner thresholds (documented).                                #
#   A defensible overall winner requires:                                      #
#     - comparable_metrics_count >= MIN_COMPARABLE_METRICS, AND               #
#     - metric_coverage_pct   >= MIN_COVERAGE_PCT, AND                         #
#     - win margin            >= MIN_WIN_MARGIN.                               #
#   Otherwise the result is "no_defensible_winner".                            #
# --------------------------------------------------------------------------- #
MIN_COMPARABLE_METRICS = 4
MIN_COVERAGE_PCT = 60.0
MIN_WIN_MARGIN = 2

# Metrics where a higher value is better; the rest use lower-absolute-is-better.
HIGHER_IS_BETTER = {"total_return_1y", "sharpe_ratio", "sortino_ratio"}
LOWER_ABS_IS_BETTER = {
    "volatility", "var_95", "cvar_95", "max_drawdown", "beta", "tracking_error",
}


def _is_finite_number(v):
    """True only for finite real numbers (not None, NaN, inf, bool, str).
    Huge integers (e.g. 10**400) that OverflowError on float() conversion are
    treated as unavailable, never as valid."""
    if v is None or isinstance(v, bool) or isinstance(v, str):
        return False
    if not isinstance(v, (int, float)):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return False
    return not (math.isnan(f) or math.isinf(f))


def _decide_overall_winner(metric_values, name_1, name_2,
                           min_comparable=MIN_COMPARABLE_METRICS,
                           min_coverage_pct=MIN_COVERAGE_PCT,
                           min_margin=MIN_WIN_MARGIN):
    """
    Pure winner-decision helper (no DB, no I/O). Unit-testable directly.

    Parameters
    ----------
    metric_values : dict[str, (value_1, value_2)]
        A metric whose value is None or non-finite is treated as UNAVAILABLE
        for BOTH portfolios (never counted as a tie or a win).
    name_1, name_2 : str
        Portfolio names.

    Returns
    -------
    dict with per-metric winner, wins_1, wins_2, ties, unavailable_count,
    comparable_metrics_count, total_metrics, metric_coverage_pct,
    overall_winner, overall_winner_key, winner_reason.

    A winner is declared only when coverage is sufficient AND the margin is
    defensible. This is a transparent HEURISTIC comparison, not a statistically
    robust investment recommendation.
    """
    total_metrics = len(metric_values)
    per_metric = {}
    wins_1 = 0
    wins_2 = 0
    ties = 0
    unavailable_count = 0

    for metric, (v1, v2) in metric_values.items():
        if not _is_finite_number(v1) or not _is_finite_number(v2):
            # NaN/inf/None -> unavailable, never an accidental tie.
            per_metric[metric] = "unavailable"
            unavailable_count += 1
            continue

        v1f = float(v1)
        v2f = float(v2)

        if metric in HIGHER_IS_BETTER:
            if v1f > v2f:
                per_metric[metric] = "portfolio_1"
                wins_1 += 1
            elif v2f > v1f:
                per_metric[metric] = "portfolio_2"
                wins_2 += 1
            else:
                per_metric[metric] = "tie"
                ties += 1
        elif metric in LOWER_ABS_IS_BETTER:
            if abs(v1f) < abs(v2f):
                per_metric[metric] = "portfolio_1"
                wins_1 += 1
            elif abs(v2f) < abs(v1f):
                per_metric[metric] = "portfolio_2"
                wins_2 += 1
            else:
                per_metric[metric] = "tie"
                ties += 1
        else:
            per_metric[metric] = "unavailable"
            unavailable_count += 1

    comparable_metrics_count = wins_1 + wins_2 + ties
    metric_coverage_pct = round(
        comparable_metrics_count / total_metrics * 100, 2
    ) if total_metrics > 0 else 0.0

    coverage_sufficient = (
        comparable_metrics_count >= min_comparable
        and metric_coverage_pct >= min_coverage_pct
    )
    margin = abs(wins_1 - wins_2)
    decisive_margin = margin >= min_margin

    if not coverage_sufficient:
        overall_winner = "no_defensible_winner"
        overall_winner_key = "no_defensible_winner"
        winner_reason = (
            f"Insufficient coverage: {comparable_metrics_count} comparable "
            f"metrics (need >= {min_comparable}) at {metric_coverage_pct}% "
            f"(need >= {min_coverage_pct}%). A winner is not defensible from "
            f"incomplete or incomparable data."
        )
    elif wins_1 == wins_2:
        # Equal wins with sufficient coverage => a genuine tie, kept SEPARATE
        # from a no-defensible-winner outcome (which is for insufficient or
        # indecisive evidence). Ties are not counted as wins.
        overall_winner = "tie"
        overall_winner_key = "tie"
        winner_reason = (
            f"Both portfolios win {wins_1} metric(s) each across "
            f"{comparable_metrics_count} comparable metrics "
            f"(coverage {metric_coverage_pct}%). A genuine tie."
        )
    elif not decisive_margin:
        # Nonzero but indecisive margin (e.g. 1) => too close to call.
        overall_winner = "no_defensible_winner"
        overall_winner_key = "no_defensible_winner"
        winner_reason = (
            f"Coverage sufficient ({comparable_metrics_count} comparable, "
            f"{metric_coverage_pct}%) but no decisive margin "
            f"({name_1}={wins_1}, {name_2}={wins_2}; need margin >= {min_margin}). "
            f"The portfolios are closely matched; no defensible winner."
        )
    elif wins_1 > wins_2:
        overall_winner = name_1
        overall_winner_key = "portfolio_1"
        winner_reason = (
            f"{name_1} wins {wins_1} of {comparable_metrics_count} comparable "
            f"metrics vs {wins_2} for {name_2} (margin {margin}, "
            f"coverage {metric_coverage_pct}%)."
        )
    else:
        overall_winner = name_2
        overall_winner_key = "portfolio_2"
        winner_reason = (
            f"{name_2} wins {wins_2} of {comparable_metrics_count} comparable "
            f"metrics vs {wins_1} for {name_1} (margin {margin}, "
            f"coverage {metric_coverage_pct}%)."
        )

    return {
        "per_metric_winner": per_metric,
        "wins_1": wins_1,
        "wins_2": wins_2,
        "ties": ties,
        "unavailable_count": unavailable_count,
        "comparable_metrics_count": comparable_metrics_count,
        "total_metrics": total_metrics,
        "metric_coverage_pct": metric_coverage_pct,
        "overall_winner": overall_winner,
        "overall_winner_key": overall_winner_key,
        "winner_reason": winner_reason,
    }


def compare_portfolios(portfolio_name_1, portfolio_name_2):

    # 1. Analyze both portfolios
    portfolio_1 = analyze_portfolio_health(portfolio_name_1)
    portfolio_2 = analyze_portfolio_health(portfolio_name_2)

    if not portfolio_1.get("success"):
        return {
            "success": False,
            "error": portfolio_1.get("error", "Portfolio 1 analysis failed.")
        }

    if not portfolio_2.get("success"):
        return {
            "success": False,
            "error": portfolio_2.get("error", "Portfolio 2 analysis failed.")
        }

    name_1 = portfolio_1["portfolio"]["portfolio_name"]
    name_2 = portfolio_2["portfolio"]["portfolio_name"]

    # 2. Prevent comparison of the same portfolio
    if name_1.lower() == name_2.lower():
        return {
            "success": False,
            "error": "Please provide two different portfolios."
        }

    # 3. Helper function for retrieving metrics
    def get_metric(data, section, metric):

        values = data.get(section)

        if not values:
            return None

        return values.get(metric)

    # 4. Define performance and risk metrics
    metric_definitions = {
        "total_return_1y": {
            "section": "performance",
            "label": "1-Year Return",
            "unit": "%"
        },
        "volatility": {
            "section": "performance",
            "label": "Volatility",
            "unit": "%"
        },
        "sharpe_ratio": {
            "section": "performance",
            "label": "Sharpe Ratio",
            "unit": ""
        },
        "max_drawdown": {
            "section": "performance",
            "label": "Maximum Drawdown",
            "unit": "%"
        },
        "beta": {
            "section": "risk_metrics",
            "label": "Beta",
            "unit": ""
        },
        "var_95": {
            "section": "risk_metrics",
            "label": "95% VaR",
            "unit": "%"
        },
        "cvar_95": {
            "section": "risk_metrics",
            "label": "95% CVaR",
            "unit": "%"
        },
        "sortino_ratio": {
            "section": "risk_metrics",
            "label": "Sortino Ratio",
            "unit": ""
        },
        "tracking_error": {
            "section": "risk_metrics",
            "label": "Tracking Error",
            "unit": "%"
        }
    }

    metric_comparison = {}

    for metric, definition in metric_definitions.items():

        value_1 = get_metric(
            portfolio_1,
            definition["section"],
            metric
        )

        value_2 = get_metric(
            portfolio_2,
            definition["section"],
            metric
        )

        # Validate finiteness. A non-finite value makes the metric unavailable
        # for that portfolio (never an accidental tie).
        v1_finite = _is_finite_number(value_1)
        v2_finite = _is_finite_number(value_2)

        if not v1_finite or not v2_finite:
            difference = None
            availability = "insufficient_data"
            # Normalise non-finite stored values to None for downstream safety.
            value_1 = float(value_1) if v1_finite else None
            value_2 = float(value_2) if v2_finite else None
        else:
            value_1 = float(value_1)
            value_2 = float(value_2)
            difference = round(value_1 - value_2, 4)
            availability = "available"

        metric_comparison[metric] = {
            "label": definition["label"],
            "portfolio_1": value_1,
            "portfolio_2": value_2,
            "difference": difference,
            "unit": definition["unit"],
            "availability": availability
        }

    # 5. Compare asset allocation
    # Distinguish "data unavailable" (no allocation records) from "actual zero"
    # (records present, asset_type absent => 0). Missing is NOT silently zero.
    def allocation_map(data):
        rows = data.get("asset_allocation") or []
        if not rows:
            return None  # data unavailable
        return {
            row["asset_type"]: row["allocation_percentage"]
            for row in rows
        }

    allocation_1 = allocation_map(portfolio_1)
    allocation_2 = allocation_map(portfolio_2)
    alloc_1_available = allocation_1 is not None
    alloc_2_available = allocation_2 is not None

    all_asset_types = sorted(
        (set(allocation_1) if alloc_1_available else set())
        | (set(allocation_2) if alloc_2_available else set())
    )

    asset_allocation_comparison = {}

    for asset_type in all_asset_types:
        # Actual zero = data available and asset_type not present.
        # Unavailable = data not available for that portfolio.
        if alloc_1_available:
            v1 = allocation_1.get(asset_type, 0)
        else:
            v1 = None
        if alloc_2_available:
            v2 = allocation_2.get(asset_type, 0)
        else:
            v2 = None

        if v1 is not None and v2 is not None:
            diff = round(v1 - v2, 2)
        else:
            diff = None

        asset_allocation_comparison[asset_type] = {
            "portfolio_1": v1,
            "portfolio_2": v2,
            "difference": diff,
            "portfolio_1_available": alloc_1_available,
            "portfolio_2_available": alloc_2_available,
        }

    # 6. Compare sector exposure (same unavailable-vs-zero distinction)
    def sector_map(data):
        rows = data.get("sector_exposures") or []
        if not rows:
            return None
        return {
            row["sector_name"]: row["exposure_percentage"]
            for row in rows
        }

    sectors_1 = sector_map(portfolio_1)
    sectors_2 = sector_map(portfolio_2)
    sec_1_available = sectors_1 is not None
    sec_2_available = sectors_2 is not None

    all_sectors = sorted(
        (set(sectors_1) if sec_1_available else set())
        | (set(sectors_2) if sec_2_available else set())
    )

    sector_comparison = {}

    for sector in all_sectors:
        if sec_1_available:
            v1 = sectors_1.get(sector, 0)
        else:
            v1 = None
        if sec_2_available:
            v2 = sectors_2.get(sector, 0)
        else:
            v2 = None

        if v1 is not None and v2 is not None:
            diff = round(v1 - v2, 2)
        else:
            diff = None

        sector_comparison[sector] = {
            "portfolio_1": v1,
            "portfolio_2": v2,
            "difference": diff,
            "portfolio_1_available": sec_1_available,
            "portfolio_2_available": sec_2_available,
        }

    # 7. Compare sector concentration
    concentration_1 = portfolio_1.get("sector_concentration") or {}
    concentration_2 = portfolio_2.get("sector_concentration") or {}

    concentration_comparison = {
        "hhi": {
            "portfolio_1": concentration_1.get("hhi"),
            "portfolio_2": concentration_2.get("hhi")
        },
        "effective_number_of_sectors": {
            "portfolio_1": concentration_1.get(
                "effective_number_of_sectors"
            ),
            "portfolio_2": concentration_2.get(
                "effective_number_of_sectors"
            )
        }
    }

    # 8. Compare data quality
    data_quality = {
        "portfolio_1": {
            "analysis_status": portfolio_1.get("analysis_status"),
            "unallocated_allocation": portfolio_1.get(
                "unallocated_allocation"
            ),
            "missing_sector_exposure": portfolio_1.get(
                "missing_sector_exposure"
            )
        },
        "portfolio_2": {
            "analysis_status": portfolio_2.get("analysis_status"),
            "unallocated_allocation": portfolio_2.get(
                "unallocated_allocation"
            ),
            "missing_sector_exposure": portfolio_2.get(
                "missing_sector_exposure"
            )
        }
    }

    # 9. Determine per-metric winner and overall winner via the pure helper.
    # Coverage threshold: >= MIN_COMPARABLE_METRICS (4) AND >= MIN_COVERAGE_PCT (60%).
    # A winner additionally requires a defensible margin (>= MIN_WIN_MARGIN, 2).
    metric_values = {
        metric: (item.get("portfolio_1"), item.get("portfolio_2"))
        for metric, item in metric_comparison.items()
    }

    decision = _decide_overall_winner(metric_values, name_1, name_2)

    # Stamp per-metric winner back onto the metric_comparison dicts.
    for metric, item in metric_comparison.items():
        item["winner"] = decision["per_metric_winner"][metric]

    wins_1 = decision["wins_1"]
    wins_2 = decision["wins_2"]
    ties = decision["ties"]
    unavailable_count = decision["unavailable_count"]
    comparable_metrics_count = decision["comparable_metrics_count"]
    TOTAL_METRICS = decision["total_metrics"]
    metric_coverage_pct = decision["metric_coverage_pct"]
    overall_winner = decision["overall_winner"]
    overall_winner_key = decision["overall_winner_key"]
    winner_reason = decision["winner_reason"]

    # 9a. Brief comparison summary
    comparison_summary = (
        f"Comparable metrics: {comparable_metrics_count}/{TOTAL_METRICS} "
        f"({metric_coverage_pct}% coverage; threshold {MIN_COVERAGE_PCT}% / "
        f"{MIN_COMPARABLE_METRICS} metrics). "
        f"{name_1} wins {wins_1}, {name_2} wins {wins_2}, ties {ties}, "
        f"unavailable {unavailable_count}. "
        f"Result: {overall_winner}. Reason: {winner_reason}"
    )
    data_dates = {
        "portfolio_1_performance_date": (
            portfolio_1["performance"]["performance_date"]
            if portfolio_1["performance"] else None
        ),
        "portfolio_2_performance_date": (
            portfolio_2["performance"]["performance_date"]
            if portfolio_2["performance"] else None
        ),
        "portfolio_1_risk_date": (
            portfolio_1["risk_metrics"]["calculation_date"]
            if portfolio_1["risk_metrics"] else None
        ),
        "portfolio_2_risk_date": (
            portfolio_2["risk_metrics"]["calculation_date"]
            if portfolio_2["risk_metrics"] else None
        )
    }

    # 11. Return complete comparison
    return {
        "success": True,
        "portfolio_1": name_1,
        "portfolio_2": name_2,
        "performance_and_risk": metric_comparison,
        "overall_winner": overall_winner,
        "overall_winner_key": overall_winner_key,
        "winner_reason": winner_reason,
        "wins_portfolio_1": wins_1,
        "wins_portfolio_2": wins_2,
        "ties": ties,
        "total_metrics": TOTAL_METRICS,
        "comparable_metrics_count": comparable_metrics_count,
        "unavailable_metric_count": unavailable_count,
        "metric_coverage_pct": metric_coverage_pct,
        "comparison_summary": comparison_summary,
        "winner_note": (
            "Winner per metric: higher return/ratio = better; "
            "lower absolute value for risk metrics (beta, VaR, CVaR, "
            "volatility, drawdown, tracking error) = better. "
            "An overall winner is declared only when comparable metrics >= "
            f"{MIN_COMPARABLE_METRICS} AND coverage >= {MIN_COVERAGE_PCT}% "
            f"AND a win margin >= {MIN_WIN_MARGIN}. Otherwise the result is "
            "'no_defensible_winner'. A tie is reported only when coverage is "
            "sufficient but wins are equal. NaN/infinity/None inputs are "
            "treated as unavailable, never as accidental ties. Missing "
            "allocation/sector values are reported as unavailable (None), "
            "not silently as zero. This is a transparent HEURISTIC comparison "
            "of nine correlated financial metrics, NOT a statistically robust "
            "investment recommendation."
        ),
        "asset_allocation_comparison": asset_allocation_comparison,
        "sector_exposure_comparison": sector_comparison,
        "concentration_comparison": concentration_comparison,
        "data_quality": data_quality,
        "data_dates": data_dates,
        "data_note": (
            "Comparisons use the latest available dataset records. "
            "Missing metrics are reported as unavailable, not estimated. "
            "No winner is fabricated from incomplete or incomparable data. "
            "The metric count is a heuristic, not investment advice."
        )
    }
