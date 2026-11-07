
from portfolio_health import analyze_portfolio_health


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

        if value_1 is None or value_2 is None:
            difference = None
            availability = "insufficient_data"

        else:
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
    def allocation_map(data):

        return {
            row["asset_type"]: row["allocation_percentage"]
            for row in data.get("asset_allocation", [])
        }

    allocation_1 = allocation_map(portfolio_1)
    allocation_2 = allocation_map(portfolio_2)

    all_asset_types = sorted(
        set(allocation_1) | set(allocation_2)
    )

    asset_allocation_comparison = {}

    for asset_type in all_asset_types:

        value_1 = allocation_1.get(asset_type, 0)
        value_2 = allocation_2.get(asset_type, 0)

        asset_allocation_comparison[asset_type] = {
            "portfolio_1": value_1,
            "portfolio_2": value_2,
            "difference": round(value_1 - value_2, 2)
        }

    # 6. Compare sector exposure
    def sector_map(data):

        return {
            row["sector_name"]: row["exposure_percentage"]
            for row in data.get("sector_exposures", [])
        }

    sectors_1 = sector_map(portfolio_1)
    sectors_2 = sector_map(portfolio_2)

    all_sectors = sorted(
        set(sectors_1) | set(sectors_2)
    )

    sector_comparison = {}

    for sector in all_sectors:

        value_1 = sectors_1.get(sector, 0)
        value_2 = sectors_2.get(sector, 0)

        sector_comparison[sector] = {
            "portfolio_1": value_1,
            "portfolio_2": value_2,
            "difference": round(value_1 - value_2, 2)
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

        # 10. Capture dates of underlying records
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
        "asset_allocation_comparison": asset_allocation_comparison,
        "sector_exposure_comparison": sector_comparison,
        "concentration_comparison": concentration_comparison,
        "data_quality": data_quality,
        "data_dates": data_dates,
        "data_note": (
            "Comparisons use the latest available dataset records. "
            "Missing metrics are reported as unavailable, not estimated."
        )
    }
