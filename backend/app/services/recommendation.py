"""Stockout-risk detection and budget-aware purchase recommendation.

--------------------------------------------------------------------------
How a product's need is worked out (spec 4.7 / 4.8)
--------------------------------------------------------------------------
    daily_rate       = forecast_demand / horizon_days
    lead_time_demand = daily_rate x reorder_lead_time_days      (0 if unknown)
    safety_stock     = safety_margin_pct x (forecast_demand + lead_time_demand)
    projected_need   = forecast_demand + lead_time_demand + safety_stock
    shortage         = ceil(max(0, projected_need - current_stock))

A product is **at risk** when ``shortage > 0`` - i.e. what we expect to sell
over the horizon (plus the cover needed while a new delivery is on its way, plus
the safety margin) exceeds what is on the shelf today.

--------------------------------------------------------------------------
Priority score (only matters when the budget cannot cover everything)
--------------------------------------------------------------------------
UPDATED: four normalised 0-1 factors, combined with explicit weights:

    priority = 0.40 x stockout_risk
             + 0.30 x normalised_forecast_demand
             + 0.20 x normalised_expected_gross_profit
             + 0.10 x normalised_affordability

* ``stockout_risk``   = shortage / projected_need, used AS-IS (not min-max
  re-scaled across the batch). This ratio already means something on its own
  - "what fraction of what I need am I missing" - and min-maxing it across
  whichever products happen to be in this run would distort that meaning
  (e.g. if every candidate this run is badly short, min-max would flatten
  that into "half urgent, half not", which is wrong).
* ``forecast_demand`` = the product's forecast_demand for this run, min-max
  normalised across all candidates. (Equivalent in ranking terms to
  normalising daily_rate, since every candidate in a run shares the same
  horizon_days - but this matches the spec's wording directly.)
* ``expected_gross_profit`` = forecast_demand x (selling_price - unit_cost),
  min-max normalised across all candidates.
* ``affordability`` = 1 / (1 + required_cost), where required_cost is what
  it would cost to fully cover this product's shortage. Min-max normalised
  across all candidates, same as the other three factors.

``cost_efficiency_score`` (margin per shilling spent) is still computed and
stored on every recommendation, since other parts of the app may read it -
it just no longer feeds priority_score directly.

Weights are configurable via settings.weight_stockout_risk,
settings.weight_forecast_demand, settings.weight_expected_gross_profit and
settings.weight_affordability (env vars DUKASMART_WEIGHT_STOCKOUT_RISK,
DUKASMART_WEIGHT_FORECAST_DEMAND, DUKASMART_WEIGHT_EXPECTED_GROSS_PROFIT,
DUKASMART_WEIGHT_AFFORDABILITY), validated at import time in config.py to
sum to 1.0. Every run stores the weights it used in weights_used, so an old
recommendation stays explainable even after the weights change.

--------------------------------------------------------------------------
Budget allocation
--------------------------------------------------------------------------
If ``total_required_cost <= budget``: everyone gets their full required quantity.

Otherwise: walk the list top-down by priority rank, giving each product as much
as the remaining budget allows (a partial fill is better than nothing). If a
product cannot be afforded at all we keep walking - a cheaper item further down
may still fit. This is a greedy allocation, chosen because it is explainable to
a shop owner; an optimal knapsack solve would buy marginally more units but
could not be justified line-by-line.

UNCHANGED by this update. The "total expected gross profit of the basket" is
computed from what's actually allocated (gross_profit_per_unit x
recommended_quantity for each line, summed), not from full forecast demand -
so a partially-funded product only contributes its partial share.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    Budget,
    DataSufficiency,
    Forecast,
    Product,
    Recommendation,
    RecommendationRun,
    RecommendationStatus,
    User,
)
from .forecasting import generate_forecasts, latest_forecasts
from .inventory import BusinessRuleError, current_stock_map, latest_unit_costs


# --------------------------------------------------------------------------
# Risk assessment
# --------------------------------------------------------------------------
def _need_profile(
    *,
    forecast_demand: float,
    horizon_days: int,
    lead_time_days: int | None,
    safety_margin_pct: float,
    current_stock: int,
) -> dict:
    daily_rate = forecast_demand / horizon_days if horizon_days else 0.0
    lead_time_demand = daily_rate * (lead_time_days or 0)
    safety_stock = safety_margin_pct * (forecast_demand + lead_time_demand)
    projected_need = forecast_demand + lead_time_demand + safety_stock
    shortage = max(0.0, projected_need - current_stock)
    return {
        "daily_rate": daily_rate,
        "lead_time_demand": lead_time_demand,
        "safety_stock": safety_stock,
        "projected_need": projected_need,
        "shortage": int(math.ceil(shortage)),
        "days_of_cover": (current_stock / daily_rate) if daily_rate > 0 else None,
    }


def assess_stock_risk(
    db: Session,
    *,
    horizon_days: int,
    safety_margin_pct: float | None = None,
    product_ids: list[int] | None = None,
) -> list[dict]:
    """Per-product risk rows for the dashboard ("Products running low")."""
    safety_margin_pct = (
        settings.default_safety_margin_pct if safety_margin_pct is None else safety_margin_pct
    )

    stmt = select(Product).where(Product.is_active.is_(True))
    if product_ids:
        stmt = stmt.where(Product.id.in_(product_ids))
    products = db.execute(stmt.order_by(Product.name)).scalars().all()
    ids = [p.id for p in products]

    stock = current_stock_map(db, ids)
    forecasts = latest_forecasts(db, horizon_days=horizon_days, product_ids=ids)

    rows: list[dict] = []
    for product in products:
        forecast = forecasts.get(product.id)
        on_hand = stock.get(product.id, 0)

        if forecast is None:
            rows.append(
                _risk_row(
                    product,
                    on_hand,
                    horizon_days,
                    status="Not forecast yet",
                    reason="No forecast has been generated for this product yet. "
                    "Run 'Update forecasts' to include it.",
                )
            )
            continue

        if forecast.data_sufficiency_flag != DataSufficiency.sufficient:
            rows.append(
                _risk_row(
                    product,
                    on_hand,
                    horizon_days,
                    status="Not enough sales history",
                    reason=forecast.insufficiency_reason
                    or "Not enough sales history to forecast this product yet.",
                    forecast_id=forecast.id,
                )
            )
            continue

        profile = _need_profile(
            forecast_demand=float(forecast.predicted_quantity or 0.0),
            horizon_days=forecast.horizon_days,
            lead_time_days=product.reorder_lead_time_days,
            safety_margin_pct=safety_margin_pct,
            current_stock=on_hand,
        )
        at_risk = profile["shortage"] > 0
        cover = profile["days_of_cover"]

        if at_risk:
            status = "Running low"
            reason = (
                f"Expect to sell about {float(forecast.predicted_quantity or 0):.0f} in the next "
                f"{horizon_days} days; only {on_hand} on the shelf. "
                f"Short by about {profile['shortage']}."
            )
        else:
            status = "Stock is fine"
            cover_text = f"about {cover:.0f} days of cover" if cover is not None else "healthy cover"
            reason = f"{on_hand} in stock covers the next {horizon_days} days ({cover_text})."

        rows.append(
            {
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "current_stock": on_hand,
                "horizon_days": horizon_days,
                "forecast_demand": round(float(forecast.predicted_quantity or 0.0), 2),
                "lead_time_demand": round(profile["lead_time_demand"], 2),
                "safety_stock": round(profile["safety_stock"], 2),
                "projected_need": round(profile["projected_need"], 2),
                "estimated_shortage": profile["shortage"],
                "at_risk": at_risk,
                "days_of_cover": None if cover is None else round(cover, 1),
                "status": status,
                "reason": reason,
                "forecast_id": forecast.id,
                "model_used": forecast.model_used,
            }
        )

    # Most urgent first.
    rows.sort(key=lambda r: (not r["at_risk"], -(r["estimated_shortage"] or 0), r["name"]))
    return rows


def _risk_row(product, on_hand, horizon_days, *, status, reason, forecast_id=None) -> dict:
    return {
        "product_id": product.id,
        "name": product.name,
        "sku": product.sku,
        "current_stock": on_hand,
        "horizon_days": horizon_days,
        "forecast_demand": None,
        "lead_time_demand": 0.0,
        "safety_stock": 0.0,
        "projected_need": None,
        "estimated_shortage": 0,
        "at_risk": False,
        "days_of_cover": None,
        "status": status,
        "reason": reason,
        "forecast_id": forecast_id,
        "model_used": None,
    }


# --------------------------------------------------------------------------
# Normalisation helper
# --------------------------------------------------------------------------
def _normalise(values: list[float]) -> list[float]:
    """Min-max scale to 0-1. All-equal inputs map to 1.0 (no product penalised)."""
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-12:
        return [1.0 for _ in values]
    return [(v - low) / (high - low) for v in values]


# --------------------------------------------------------------------------
# NEW: short, skimmable "what drove this ranking" label
# --------------------------------------------------------------------------
def _priority_label(
    *,
    risk: float,
    demand: float,
    profit: float,
    affordability: float,
    weight_stockout_risk: float,
    weight_forecast_demand: float,
    weight_expected_gross_profit: float,
    weight_affordability: float,
) -> str:
    """One-line tag for a table column, e.g. 'High demand + high margin' or
    'Urgent: stockout risk'. Distinct from `reason`, which stays a full
    paragraph - this is meant to be skimmed at a glance.
    """
    if risk >= 0.8:
        # A near-empty shelf dominates how this line should read, regardless
        # of the other three factors' weighted contribution.
        return "Urgent: stockout risk"

    contributions = {
        "stockout risk": weight_stockout_risk * risk,
        "high demand": weight_forecast_demand * demand,
        "high margin": weight_expected_gross_profit * profit,
        "affordability": weight_affordability * affordability,
    }
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    top_name, top_value = ranked[0]
    second_name, second_value = ranked[1]

    if top_value <= 0:
        return "Balanced priority"

    if second_value > 0 and second_value >= top_value * 0.6:
        # Two factors are close enough that both deserve credit.
        return f"{top_name.capitalize()} + {second_name}"

    return top_name.capitalize()


# --------------------------------------------------------------------------
# The recommendation run
# --------------------------------------------------------------------------
def generate_recommendation_run(
    db: Session,
    *,
    user: User,
    budget_id: int,
    horizon_days: int,
    safety_margin_pct: float,
    refresh_forecasts: bool = True,
    as_of: date | None = None,
) -> RecommendationRun:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise BusinessRuleError("That budget was not found. Create a budget first.")
    if budget.amount_available <= 0:
        raise BusinessRuleError("The budget must be more than zero.")

    with db.begin_nested():
        if refresh_forecasts:
            generate_forecasts(db, horizon_days=horizon_days, as_of=as_of)

        products = (
            db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.name))
            .scalars()
            .all()
        )
        ids = [p.id for p in products]
        stock = current_stock_map(db, ids)
        forecasts = latest_forecasts(db, horizon_days=horizon_days, product_ids=ids)
        costs = latest_unit_costs(db, ids)

        candidates: list[dict] = []
        skipped_no_forecast = 0
        skipped_no_cost = 0

        for product in products:
            forecast = forecasts.get(product.id)
            if forecast is None or forecast.data_sufficiency_flag != DataSufficiency.sufficient:
                skipped_no_forecast += 1
                continue

            on_hand = stock.get(product.id, 0)
            demand = float(forecast.predicted_quantity or 0.0)
            profile = _need_profile(
                forecast_demand=demand,
                horizon_days=forecast.horizon_days,
                lead_time_days=product.reorder_lead_time_days,
                safety_margin_pct=safety_margin_pct,
                current_stock=on_hand,
            )
            if profile["shortage"] <= 0:
                continue  # not at risk - nothing to buy

            unit_cost = float(costs.get(product.id) or product.default_unit_cost or 0.0)
            if unit_cost <= 0:
                # We cannot budget for something with no known purchase cost.
                skipped_no_cost += 1
                continue

            # --- NEW: profitability figures, computed once per candidate ---
            gross_profit_per_unit = float(product.selling_price) - unit_cost
            expected_gross_profit = demand * gross_profit_per_unit
            # --- end new ---

            candidates.append(
                {
                    "product": product,
                    "forecast": forecast,
                    "current_stock": on_hand,
                    "forecast_demand": demand,
                    "unit_cost": unit_cost,
                    "gross_profit_per_unit": gross_profit_per_unit,
                    "expected_gross_profit": expected_gross_profit,
                    **profile,
                }
            )

        # ---- scoring ---------------------------------------------------
        if candidates:
            velocities = [c["daily_rate"] for c in candidates]
            margins = [
                max(0.0, float(c["product"].selling_price) - c["unit_cost"]) / c["unit_cost"]
                for c in candidates
            ]
            if max(margins) <= 0:
                # No margin data worth using -> fall back to cheap-first.
                margins = [1.0 / c["unit_cost"] for c in candidates]

            velocity_scores = _normalise(velocities)
            cost_scores = _normalise(margins)

            # --- NEW: the four factors that actually feed priority_score now ---
            demand_scores = _normalise([c["forecast_demand"] for c in candidates])
            profit_scores = _normalise([c["expected_gross_profit"] for c in candidates])
            required_costs = [c["shortage"] * c["unit_cost"] for c in candidates]
            affordability_raw = [1.0 / (1.0 + rc) for rc in required_costs]
            affordability_scores = _normalise(affordability_raw)
            # --- end new ---

            for c, vel, ce, dem, prof, afford in zip(
                candidates,
                velocity_scores,
                cost_scores,
                demand_scores,
                profit_scores,
                affordability_scores,
                strict=True,
            ):
                risk = (
                    min(1.0, c["shortage"] / c["projected_need"]) if c["projected_need"] > 0 else 0.0
                )
                c["stockout_risk_score"] = risk
                c["demand_velocity_score"] = vel
                # Still computed and stored for backward compatibility / other
                # reports, but no longer part of priority_score below.
                c["cost_efficiency_score"] = ce

                # --- NEW: the updated 4-factor weighted priority score ---
                c["priority_score"] = (
                    settings.weight_stockout_risk * risk
                    + settings.weight_forecast_demand * dem
                    + settings.weight_expected_gross_profit * prof
                    + settings.weight_affordability * afford
                )
                c["priority_label"] = _priority_label(
                    risk=risk,
                    demand=dem,
                    profit=prof,
                    affordability=afford,
                    weight_stockout_risk=settings.weight_stockout_risk,
                    weight_forecast_demand=settings.weight_forecast_demand,
                    weight_expected_gross_profit=settings.weight_expected_gross_profit,
                    weight_affordability=settings.weight_affordability,
                )
                # --- end new ---

            # Highest priority first; cheaper line wins a tie so the budget stretches.
            candidates.sort(
                key=lambda c: (-c["priority_score"], c["shortage"] * c["unit_cost"], c["product"].name)
            )

        total_required = sum(c["shortage"] * c["unit_cost"] for c in candidates)
        budget_amount = float(budget.amount_available)
        constrained = total_required > budget_amount + 1e-9

        run = RecommendationRun(
            user_id=user.id,
            budget_id=budget.id,
            horizon_days=horizon_days,
            safety_margin_pct=safety_margin_pct,
            budget_amount=budget_amount,
            total_required_cost=round(total_required, 2),
            total_recommended_cost=0.0,
            budget_constrained=constrained,
            weights_used=json.dumps(
                {
                    "stockout_risk": settings.weight_stockout_risk,
                    "forecast_demand": settings.weight_forecast_demand,
                    "expected_gross_profit": settings.weight_expected_gross_profit,
                    "affordability": settings.weight_affordability,
                }
            ),
            products_considered=len(candidates),
            products_skipped_no_forecast=skipped_no_forecast,
            products_skipped_no_cost=skipped_no_cost,
        )
        db.add(run)
        db.flush()

        # ---- allocation -------------------------------------------------
        remaining = budget_amount
        total_allocated = 0.0

        for rank, c in enumerate(candidates, start=1):
            required_qty = int(c["shortage"])
            unit_cost = c["unit_cost"]
            required_cost = required_qty * unit_cost

            if not constrained:
                allocated_qty = required_qty
            else:
                affordable = int(math.floor((remaining + 1e-9) / unit_cost))
                allocated_qty = max(0, min(required_qty, affordable))

            allocated_cost = round(allocated_qty * unit_cost, 2)
            remaining -= allocated_cost
            total_allocated += allocated_cost

            db.add(
                Recommendation(
                    run_id=run.id,
                    product_id=c["product"].id,
                    forecast_id=c["forecast"].id,
                    current_stock=c["current_stock"],
                    forecast_demand=round(c["forecast_demand"], 3),
                    safety_stock=round(c["safety_stock"], 3),
                    lead_time_demand=round(c["lead_time_demand"], 3),
                    estimated_shortage=required_qty,
                    unit_cost=round(unit_cost, 2),
                    required_quantity=required_qty,
                    required_cost=round(required_cost, 2),
                    recommended_quantity=allocated_qty,
                    recommended_cost=allocated_cost,
                    stockout_risk_score=round(c["stockout_risk_score"], 4),
                    demand_velocity_score=round(c["demand_velocity_score"], 4),
                    cost_efficiency_score=round(c["cost_efficiency_score"], 4),
                    priority_score=round(c["priority_score"], 4),
                    priority_rank=rank,
                    reason=_explain(c, required_qty, allocated_qty, rank, constrained),
                    # --- NEW: profitability-aware columns ---
                    gross_profit_per_unit=round(c["gross_profit_per_unit"], 2),
                    expected_gross_profit=round(c["expected_gross_profit"], 2),
                    priority_reason=c["priority_label"],
                    # --- end new ---
                    status=RecommendationStatus.proposed,
                )
            )

        run.total_recommended_cost = round(total_allocated, 2)
        # NOTE: total_expected_gross_profit is intentionally NOT set here as a
        # Python attribute. An earlier draft did that, but it only survives
        # for a run fetched in the same request/session it was generated in -
        # any later fetch (list_runs, latest_run, get_run in planning.py)
        # would silently see 0 instead of the real total. Since
        # gross_profit_per_unit and recommended_quantity are both persisted
        # columns on every Recommendation row, the router derives this total
        # from the database instead (see _run_out in routers/planning.py),
        # which works correctly for every run, old or new.
        db.flush()

    return run


def _explain(c: dict, required_qty: int, allocated_qty: int, rank: int, constrained: bool) -> str:
    """Plain-language 'why this line' text shown next to every recommendation.

    Unchanged by the profitability update - this stays the detailed
    paragraph it always was. The new short priority label lives in
    `priority_reason` instead (see `_priority_label` above), so nothing here
    needed to change.
    """
    product = c["product"]
    horizon = c["forecast"].horizon_days
    parts = [
        f"You have {c['current_stock']} {product.name} left.",
        f"Sales are running at about {c['daily_rate']:.1f} a day, so you should sell roughly "
        f"{c['forecast_demand']:.0f} over the next {horizon} days.",
    ]
    if c["lead_time_demand"] > 0:
        parts.append(
            f"Allowing {product.reorder_lead_time_days} day(s) for delivery adds about "
            f"{c['lead_time_demand']:.0f} more."
        )
    parts.append(
        f"With a safety cushion of {c['safety_stock']:.0f}, you are short about {required_qty}."
    )
    if allocated_qty == 0:
        parts.append("There is no budget left for this one after the higher-priority items.")
    elif allocated_qty < required_qty:
        parts.append(
            f"Budget only stretches to {allocated_qty} of the {required_qty} needed "
            f"(priority #{rank})."
        )
    elif constrained:
        parts.append(f"Fully covered as priority #{rank}.")
    else:
        parts.append("The budget covers everything needed.")
    return " ".join(parts)


# --------------------------------------------------------------------------
# Operator decisions
# --------------------------------------------------------------------------
def apply_decision(
    db: Session, *, recommendation_id: int, status: RecommendationStatus, quantity: int | None
) -> Recommendation:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise BusinessRuleError("That recommendation line was not found.")

    if status == RecommendationStatus.modified:
        if quantity is None:
            raise BusinessRuleError("Enter the quantity you want to buy.")
        if quantity < 0:
            raise BusinessRuleError("Quantity cannot be negative.")
        rec.operator_quantity = int(quantity)
    elif status == RecommendationStatus.accepted:
        rec.operator_quantity = rec.recommended_quantity
    elif status == RecommendationStatus.rejected:
        rec.operator_quantity = 0

    rec.status = status
    rec.decided_at = datetime.now(timezone.utc)
    db.flush()
    return rec
