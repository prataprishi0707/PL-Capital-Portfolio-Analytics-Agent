"""
PL Capital Portfolio Reconciliation Engine (v3 — partial-denominator rejection).

CORE PRINCIPLE: a normalised weight is only meaningful when computed over a
COMPLETE denominator. If any holding required for the market-value denominator
is missing or invalid, NO holding receives a normalised market-value weight,
and no holding is marked MATCHED on the basis of a partial denominator.

Status vocabulary:
    MATCHED            — every holding comparable, all within warning threshold.
    OBSERVATION        — every holding comparable, >=1 within warning, none error.
    DISCREPANCY_FOUND  — every holding comparable, >=1 within error threshold, OR
                         the recorded allocation drift exceeds the error threshold.
    INCOMPLETE         — >=1 required holding cannot be compared (missing price,
                         missing quantity, missing weight) so a full reconciliation
                         is impossible. Partial denominators are NOT normalised.
    INVALID_DATA       — >=1 holding contains NaN, infinity, an invalid string, or
                         a disallowed negative value. Distinct from INCOMPLETE.

Three independent axes are reported:
    (1) Per-holding market-value weight drift (vs recorded current_weight).
    (2) Allocation drift: do recorded weights sum to 1.0?  INCOMPLETE if any
        recorded weight is missing/invalid — we never sum only the available
        weights and call the result MATCHED.
    (3) AUM coverage: market value vs recorded AUM. INFORMATIONAL. Never presented
        as full portfolio coverage when the market-value denominator is partial.

A cost-basis diagnostic weight is computed when the cost-basis denominator is
complete; otherwise it is marked unavailable (partial cost-basis is not normalised).

All numeric inputs are strictly validated (NULL is missing not zero; NaN/inf/
invalid strings/negatives rejected). No financial data is fabricated.
"""

import math
import sqlite3
from database import get_connection, _authorizer


# --------------------------------------------------------------------------- #
# Thresholds (decimal fractions, matching stored current_weight units)        #
# --------------------------------------------------------------------------- #
WARNING_THRESHOLD = 0.005   # 0.5 percentage points
ERROR_THRESHOLD = 0.020     # 2.0 percentage points
TOTAL_WEIGHT_WARNING = 0.005
TOTAL_WEIGHT_ERROR = 0.020

# Explicit status vocabulary
STATUS_MATCHED = "MATCHED"
STATUS_OBSERVATION = "OBSERVATION"
STATUS_DISCREPANCY = "DISCREPANCY_FOUND"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_INVALID = "INVALID_DATA"

# Aggregate priority — worst applicable condition wins.
# INVALID_DATA (broken data) > INCOMPLETE (cannot fully assess) >
# DISCREPANCY_FOUND (verified problem) > OBSERVATION > MATCHED.
_AGG_PRIORITY = {
    STATUS_INVALID: 5,
    STATUS_INCOMPLETE: 4,
    STATUS_DISCREPANCY: 3,
    STATUS_OBSERVATION: 2,
    STATUS_MATCHED: 1,
}

_STATUS_TO_LEGACY = {
    STATUS_MATCHED: "clean",
    STATUS_OBSERVATION: "warnings",
    STATUS_DISCREPANCY: "errors",
    STATUS_INCOMPLETE: "incomplete",
    STATUS_INVALID: "invalid_data",
}


# --------------------------------------------------------------------------- #
# Strict numeric validation                                                     #
# --------------------------------------------------------------------------- #
def validate_numeric(value, field_name, *, allow_none=False, allow_zero=True,
                      allow_negative=False):
    """
    Strictly validate a numeric field.

    Returns: (status, cleaned_value, error_message)
        status: "valid" | "missing" | "invalid"
    """
    if value is None:
        if allow_none:
            return ("valid", None, None)
        return ("missing", None, f"{field_name} is NULL (missing).")

    if isinstance(value, bool):
        return ("invalid", None, f"{field_name} is a boolean, not a number.")

    cleaned = None
    if isinstance(value, (int, float)):
        # int -> float conversion can raise OverflowError for huge integers
        # (e.g. 10**400). Treat such unrepresentable values as invalid.
        try:
            cleaned = float(value)
        except OverflowError:
            return ("invalid", None,
                    f"{field_name} is too large to represent as a float.")
    elif isinstance(value, str):
        s = value.strip()
        if s == "":
            if allow_none:
                return ("valid", None, None)
            return ("missing", None, f"{field_name} is an empty string.")
        try:
            cleaned = float(s)
        except (ValueError, TypeError):
            return ("invalid", None,
                    f"{field_name} is not a valid numeric string: {value!r}.")
    else:
        return ("invalid", None,
                f"{field_name} has unsupported type {type(value).__name__}.")

    try:
        if math.isnan(cleaned):
            return ("invalid", None, f"{field_name} is NaN.")
        if math.isinf(cleaned):
            return ("invalid", None, f"{field_name} is infinite.")
    except (TypeError, ValueError):
        return ("invalid", None, f"{field_name} could not be checked for finiteness.")

    if cleaned == 0 and not allow_zero:
        return ("invalid", None, f"{field_name} is zero, which is not permitted here.")
    if cleaned < 0 and not allow_negative:
        return ("invalid", None, f"{field_name} is negative ({cleaned}), which is not permitted.")

    return ("valid", cleaned, None)


def _safe_product(a, b):
    try:
        result = float(a) * float(b)
    except (OverflowError, ValueError, TypeError):
        return None
    if result is None or math.isnan(result) or math.isinf(result):
        return None
    return result


def _safe_sum(values):
    total = 0.0
    for v in values:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            return None
        total += f
    if math.isnan(total) or math.isinf(total):
        return None
    return total


# --------------------------------------------------------------------------- #
# Per-holding validation                                                       #
# --------------------------------------------------------------------------- #
def reconcile_holding(raw_holding):
    """
    Validate a single holding dict. Does NOT assign MATCHED/OBSERVATION/DISCREPANCY
    (those require the portfolio denominator). Returns per-field validation errors
    and one of: INVALID_DATA, INCOMPLETE, or None (pending — awaiting denominator).
    """
    errors = {}

    q_status, q_val, q_err = validate_numeric(
        raw_holding.get("quantity"), "quantity",
        allow_none=False, allow_zero=False, allow_negative=False)
    p_status, p_val, p_err = validate_numeric(
        raw_holding.get("current_price"), "current_price",
        allow_none=True, allow_zero=False, allow_negative=False)
    w_status, w_val, w_err = validate_numeric(
        raw_holding.get("current_weight"), "current_weight",
        allow_none=False, allow_zero=True, allow_negative=False)
    cb_status, cb_val, cb_err = validate_numeric(
        raw_holding.get("cost_basis"), "cost_basis",
        allow_none=True, allow_zero=False, allow_negative=False)

    if q_status != "valid":
        errors["quantity"] = q_err
    if p_status == "invalid":
        errors["current_price"] = p_err
    if w_status != "valid":
        errors["current_weight"] = w_err
    if cb_status == "invalid":
        errors["cost_basis"] = cb_err

    has_invalid = any(s == "invalid" for s in (q_status, p_status, w_status, cb_status))

    recorded_weight = w_val if w_status == "valid" else None
    quantity = q_val if q_status == "valid" else None
    price = p_val if p_status == "valid" else None
    cost_basis = cb_val if cb_status == "valid" else None

    market_value = None
    if quantity is not None and price is not None and not has_invalid:
        market_value = _safe_product(quantity, price)

    if has_invalid:
        status = STATUS_INVALID
    elif quantity is None or recorded_weight is None:
        status = STATUS_INCOMPLETE
    elif price is None:
        status = STATUS_INCOMPLETE
    elif market_value is None:
        # product failed (overflow etc.)
        status = STATUS_INVALID
        errors["market_value"] = "quantity * current_price overflowed or is non-finite."
    else:
        status = None  # pending — comparable once denominator is known

    return {
        "symbol": raw_holding.get("symbol"),
        "company_name": raw_holding.get("company_name"),
        "asset_type": raw_holding.get("asset_type"),
        "quantity": quantity,
        "current_price": price,
        "cost_basis": cost_basis,
        "market_value": round(market_value, 2) if market_value is not None else None,
        "_raw_market_value": market_value,
        "recorded_weight": round(recorded_weight, 6) if recorded_weight is not None else None,
        "_raw_recorded_weight": recorded_weight,
        "cost_basis_weight": None,
        "computed_weight": None,
        "weight_drift": None,
        "weight_drift_pct": None,
        "validation": errors,
        "status": status,
    }


# --------------------------------------------------------------------------- #
# Pure reconciliation core (no DB access) — unit-testable directly             #
# --------------------------------------------------------------------------- #
def _reconcile_holdings(holdings_raw, recorded_aum_raw, canonical_name):
    """
    Reconcile a list of raw holding dicts against recorded weights.

    Pure function — no database access. This is the unit-testable core.
    reconcile_portfolio() reads from the DB and delegates here.

    Partial-denominator rules:
      - market-value denominator is complete iff EVERY holding has a valid
        (quantity, price) market value AND no holding is INVALID_DATA.
      - If the market-value denominator is incomplete, no holding receives a
        normalised computed_weight; all pending holdings become INCOMPLETE.
      - Allocation drift is assessable iff every holding has a valid recorded
        weight; otherwise it is INCOMPLETE (never a partial sum).
      - Cost-basis diagnostic weights require a complete cost-basis denominator.
    """
    n = len(holdings_raw)
    holdings_detail = [reconcile_holding(h) for h in holdings_raw]

    # Validation errors
    validation_errors = [
        {"symbol": h["symbol"], "errors": h["validation"]}
        for h in holdings_detail if h["validation"]
    ]

    # Denominator completeness checks.
    any_invalid = any(h["status"] == STATUS_INVALID for h in holdings_detail)

    # Market-value denominator is complete ONLY when every holding is fully
    # comparable (status is None => valid quantity, price, AND recorded weight,
    # with a finite market value). A holding missing its recorded weight is
    # INCOMPLETE, which makes the market-value reconciliation incomplete too:
    # we cannot compute drift without a recorded weight to compare against.
    market_denominator_complete = all(h["status"] is None for h in holdings_detail)

    # Allocation drift: assessable iff every holding has a valid recorded weight
    # and no holding is INVALID_DATA.
    allocation_assessable = (
        not any_invalid
        and all(h["_raw_recorded_weight"] is not None for h in holdings_detail)
    )

    # Cost-basis denominator: complete iff every holding has a valid cost_basis.
    cost_basis_denominator_complete = (
        not any_invalid
        and all(h["cost_basis"] is not None for h in holdings_detail)
    )

    # ---- Market-value normalisation -------------------------------------- #
    total_market_value = None
    if market_denominator_complete:
        total_market_value = _safe_sum(h["_raw_market_value"] for h in holdings_detail)
        if total_market_value is None or total_market_value <= 0:
            # Degenerate denominator — treat as incomplete.
            market_denominator_complete = False
            total_market_value = None

    # Assign per-holding statuses.
    per_holding_statuses = []
    if market_denominator_complete and total_market_value is not None:
        for h in holdings_detail:
            mv = h["_raw_market_value"]
            rec_w = h["_raw_recorded_weight"]
            computed_w = mv / total_market_value
            h["computed_weight"] = round(computed_w, 6)
            drift = abs(computed_w - rec_w)
            h["weight_drift"] = round(drift, 6)
            h["weight_drift_pct"] = round(drift * 100, 4)
            if drift > ERROR_THRESHOLD:
                h["status"] = STATUS_DISCREPANCY
            elif drift > WARNING_THRESHOLD:
                h["status"] = STATUS_OBSERVATION
            else:
                h["status"] = STATUS_MATCHED
            per_holding_statuses.append(h["status"])
    else:
        # Partial denominator: no normalisation. Pending holdings -> INCOMPLETE.
        for h in holdings_detail:
            if h["status"] is None:
                h["status"] = STATUS_INCOMPLETE
            # INVALID stays INVALID; INCOMPLETE stays INCOMPLETE.
            # computed_weight / weight_drift remain None.
            per_holding_statuses.append(h["status"])

    # ---- Discrepancies (per-holding) ------------------------------------- #
    discrepancies = []
    for h in holdings_detail:
        if h["status"] in (STATUS_OBSERVATION, STATUS_DISCREPANCY):
            discrepancies.append({
                "symbol": h["symbol"],
                "recorded_weight": h["recorded_weight"],
                "computed_weight": h["computed_weight"],
                "weight_drift": h["weight_drift"],
                "weight_drift_pct": h["weight_drift_pct"],
                "cost_basis_weight": h["cost_basis_weight"],
                "severity": "error" if h["status"] == STATUS_DISCREPANCY else "warning",
            })

    # ---- Allocation drift axis ------------------------------------------- #
    allocation_drift = {
        "recorded_total_weight": None,
        "expected_total": 1.0,
        "drift": None,
        "status": None,
    }
    if allocation_assessable:
        recorded_total = _safe_sum(h["_raw_recorded_weight"] for h in holdings_detail)
        if recorded_total is None:
            allocation_drift["status"] = STATUS_INCOMPLETE
        else:
            total_drift = abs(recorded_total - 1.0)
            allocation_drift["recorded_total_weight"] = round(recorded_total, 6)
            allocation_drift["drift"] = round(total_drift, 6)
            if total_drift > TOTAL_WEIGHT_ERROR:
                allocation_drift["status"] = STATUS_DISCREPANCY
                discrepancies.append({
                    "type": "allocation_drift",
                    "recorded_total": round(recorded_total, 6),
                    "expected_total": 1.0,
                    "drift": round(total_drift, 6),
                    "severity": "error",
                })
            elif total_drift > TOTAL_WEIGHT_WARNING:
                allocation_drift["status"] = STATUS_OBSERVATION
                discrepancies.append({
                    "type": "allocation_drift",
                    "recorded_total": round(recorded_total, 6),
                    "expected_total": 1.0,
                    "drift": round(total_drift, 6),
                    "severity": "warning",
                })
            else:
                allocation_drift["status"] = STATUS_MATCHED
    else:
        # Never sum only the available weights.
        allocation_drift["status"] = STATUS_INCOMPLETE

    # ---- AUM coverage axis (informational) ------------------------------- #
    # Distinguish MISSING AUM (None) from INVALID AUM (NaN, infinity, invalid
    # string, negative). We validate with allow_none=False so that None is
    # classified explicitly as "missing" (still NOT invalid). Missing ->
    # not_assessed. Invalid -> INVALID_DATA with a validation error; coverage
    # is never computed from an invalid AUM.
    aum_status_val, aum_val, aum_err = validate_numeric(
        recorded_aum_raw, "total_aum",
        allow_none=False, allow_zero=True, allow_negative=False)

    aum_is_invalid = (aum_status_val == "invalid")
    aum_is_missing = (aum_status_val == "missing")

    aum_coverage = {
        "recorded_aum": round(aum_val, 2) if aum_val is not None else None,
        "total_market_value": round(total_market_value, 2) if total_market_value is not None else None,
        "coverage_pct": None,
        "status": None,
        "note": None,
        "aum_status": aum_status_val,  # "valid" | "missing" | "invalid" (explicit)
    }

    if aum_is_invalid:
        # Invalid AUM (NaN/inf/invalid-string/negative): INVALID_DATA, not
        # silently "missing". Do not calculate coverage from an invalid value.
        aum_coverage["status"] = STATUS_INVALID
        aum_coverage["note"] = (
            f"Recorded AUM is invalid ({aum_err}); AUM coverage cannot be "
            f"assessed. This is INVALID_DATA, not missing.")
        validation_errors.append({
            "symbol": canonical_name,
            "level": "portfolio",
            "errors": {"total_aum": aum_err},
        })
    elif not market_denominator_complete:
        # Partial market value — never present as full coverage.
        aum_coverage["status"] = STATUS_INCOMPLETE
        aum_coverage["note"] = (
            "Market-value denominator is incomplete; AUM coverage cannot be "
            "assessed from a partial market value.")
    elif aum_is_missing or aum_val is None or aum_val == 0:
        # Missing or zero AUM (valid but uninformative) -> not_assessed.
        aum_coverage["status"] = "not_assessed"
        if aum_is_missing:
            aum_coverage["note"] = "Recorded AUM is missing; coverage cannot be assessed."
        elif aum_val == 0:
            aum_coverage["note"] = "Recorded AUM is zero; coverage cannot be assessed."
        else:
            aum_coverage["note"] = "Recorded AUM is unavailable; coverage cannot be assessed."
    elif total_market_value is None or total_market_value <= 0:
        aum_coverage["status"] = "not_assessed"
        aum_coverage["note"] = "Total market value is unavailable; coverage cannot be assessed."
    else:
        cov = (total_market_value / aum_val) * 100.0
        aum_coverage["coverage_pct"] = round(cov, 2)
        if cov < 5.0 or cov > 200.0:
            aum_coverage["status"] = STATUS_OBSERVATION
            aum_coverage["note"] = (
                "Market value differs from recorded AUM by an extreme margin. "
                "Informational: prices in the securities table are not the "
                "lot-purchase prices used to size AUM.")
        else:
            aum_coverage["status"] = STATUS_MATCHED
            aum_coverage["note"] = (
                "Market value and recorded AUM are within a plausible range. "
                "Coverage is informational, not a pass/fail reconciliation axis.")

    # ---- Cost-basis diagnostic ------------------------------------------- #
    total_cost_basis = None
    if cost_basis_denominator_complete:
        total_cost_basis = _safe_sum(h["cost_basis"] for h in holdings_detail)
        if total_cost_basis is None or total_cost_basis <= 0:
            cost_basis_denominator_complete = False
            total_cost_basis = None

    if cost_basis_denominator_complete and total_cost_basis is not None:
        for h in holdings_detail:
            h["cost_basis_weight"] = round(h["cost_basis"] / total_cost_basis, 6)
    # else: cost_basis_weight stays None for all (partial not normalised).

    # ---- Aggregate portfolio status (worst applicable condition) --------- #
    combined = list(per_holding_statuses)
    if allocation_drift["status"] is not None:
        combined.append(allocation_drift["status"])

    # Invalid AUM is a portfolio-level data-integrity defect; surface it so the
    # aggregate reflects INVALID_DATA when appropriate. (Other AUM coverage
    # statuses — MATCHED/OBSERVATION/not_assessed — do not elevate the aggregate
    # to avoid conflating an informational axis with holding-level findings.)
    if aum_coverage["status"] == STATUS_INVALID:
        combined.append(STATUS_INVALID)

    # Determine worst status present.
    if not combined:
        portfolio_status = STATUS_MATCHED
    else:
        portfolio_status = max(combined, key=lambda s: _AGG_PRIORITY.get(s, 0))

    # Duplicate securities and zero-weight holdings (data-quality observations).
    symbol_counts = {}
    for h in holdings_raw:
        sym = h.get("symbol")
        if sym is not None:
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
    duplicate_securities = [sym for sym, cnt in symbol_counts.items() if cnt > 1]

    zero_weight_holdings = [
        h["symbol"] for h in holdings_detail
        if h["recorded_weight"] is not None and h["recorded_weight"] == 0
    ]
    unpriced_holdings = [
        h["symbol"] for h in holdings_detail
        if h["current_price"] is None and h["status"] != STATUS_INVALID
    ]

    # Data completeness: fraction of holdings that were fully comparable
    # (i.e. denominator complete and holding received a real comparison).
    complete_comparable = sum(
        1 for h in holdings_detail
        if h["status"] in (STATUS_MATCHED, STATUS_OBSERVATION, STATUS_DISCREPANCY)
    )
    data_completeness_pct = round(complete_comparable / n * 100, 2) if n else 0.0

    summary = {
        "total_holdings": n,
        "matched_count": sum(1 for h in holdings_detail if h["status"] == STATUS_MATCHED),
        "observation_count": sum(1 for h in holdings_detail if h["status"] == STATUS_OBSERVATION),
        "discrepancy_count": sum(1 for h in holdings_detail if h["status"] == STATUS_DISCREPANCY),
        "incomplete_count": sum(1 for h in holdings_detail if h["status"] == STATUS_INCOMPLETE),
        "invalid_count": sum(1 for h in holdings_detail if h["status"] == STATUS_INVALID),
        "duplicate_count": len(duplicate_securities),
        "validation_error_count": len(validation_errors),
        "zero_weight_count": len(zero_weight_holdings),
    }

    return {
        "success": True,
        "portfolio_name": canonical_name,
        "status": portfolio_status,
        "reconciliation_status": _STATUS_TO_LEGACY.get(portfolio_status, "incomplete"),
        # Allocation drift axis (weights vs 1.0).
        "recorded_total_weight": allocation_drift["recorded_total_weight"],
        "weight_drift": allocation_drift["drift"],
        "allocation_drift": allocation_drift,
        # AUM coverage axis (informational).
        "aum_coverage": aum_coverage,
        "total_market_value": round(total_market_value, 2) if total_market_value is not None else None,
        "total_cost_basis": round(total_cost_basis, 2) if total_cost_basis is not None else None,
        # Denominator completeness flags (for transparency / testing).
        "market_denominator_complete": market_denominator_complete,
        "allocation_assessable": allocation_assessable,
        "cost_basis_denominator_complete": cost_basis_denominator_complete,
        # Holdings detail.
        "holdings_count": n,
        "priceable_holdings": sum(1 for h in holdings_detail if h["_raw_market_value"] is not None),
        "holdings": holdings_detail,
        "discrepancies": discrepancies,
        "duplicate_securities": duplicate_securities,
        "zero_weight_holdings": zero_weight_holdings,
        "unpriced_holdings": unpriced_holdings,
        # Validation.
        "validation_errors": validation_errors,
        "data_completeness_pct": data_completeness_pct,
        "summary": summary,
        "thresholds": {
            "warning_threshold_pct": WARNING_THRESHOLD * 100,
            "error_threshold_pct": ERROR_THRESHOLD * 100,
            "total_weight_warning_pct": TOTAL_WEIGHT_WARNING * 100,
            "total_weight_error_pct": TOTAL_WEIGHT_ERROR * 100,
        },
        "methodology": (
            "Market-value computed weight = (quantity * current_price) / "
            "sum(quantity * current_price), ONLY when the market-value "
            "denominator is complete (every holding has valid quantity and "
            "price). Partial denominators are NOT normalised. Allocation drift "
            "(recorded weights vs 1.0) is assessable only when every recorded "
            "weight is valid; a partial weight set is never summed. Cost-basis "
            "diagnostic weight = cost_basis / sum(cost_basis), only when the "
            "cost-basis denominator is complete. NULL/NaN/inf/negative values "
            "are rejected, not treated as zero. AUM coverage is informational."
        ),
        "data_note": (
            "current_price is not the lot-purchase price used to size recorded "
            "AUM. Divergence between market-value weights and recorded weights "
            "is reported, not normalised. No financial data is fabricated."
        ),
    }


# --------------------------------------------------------------------------- #
# DB-backed entry point                                                        #
# --------------------------------------------------------------------------- #
def reconcile_portfolio(portfolio_name: str) -> dict:
    """Reconcile a named portfolio from the database."""
    conn = None
    try:
        conn = get_connection(read_only=True)
        conn.set_authorizer(_authorizer)
        conn.row_factory = sqlite3.Row

        portfolio_row = conn.execute(
            "SELECT portfolio_id, portfolio_name, total_aum FROM portfolios "
            "WHERE LOWER(TRIM(portfolio_name)) = LOWER(TRIM(?))",
            (portfolio_name,)
        ).fetchone()

        if portfolio_row is None:
            return {"success": False, "error": f"Portfolio '{portfolio_name}' not found."}

        portfolio_id = portfolio_row["portfolio_id"]
        canonical_name = portfolio_row["portfolio_name"]
        recorded_aum_raw = portfolio_row["total_aum"]

        rows = conn.execute("""
            SELECT
                h.holding_id,
                h.security_id,
                s.symbol,
                s.company_name,
                s.asset_type,
                h.quantity,
                h.current_weight,
                h.cost_basis,
                s.current_price
            FROM holdings h
            JOIN securities s ON h.security_id = s.security_id
            WHERE h.portfolio_id = ?
            ORDER BY s.symbol
        """, (portfolio_id,)).fetchall()

        if not rows:
            return {"success": False, "error": f"No holdings found for '{portfolio_name}'."}

        holdings_raw = [dict(r) for r in rows]
        return _reconcile_holdings(holdings_raw, recorded_aum_raw, canonical_name)

    except Exception as exc:
        return {"success": False, "error": str(exc)}

    finally:
        if conn:
            conn.close()
