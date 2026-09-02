"""Budget-aware recommendation: risk detection, prioritisation, allocation, decisions."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from app.models import Budget, DataSufficiency, RecommendationStatus
from app.services.inventory import BusinessRuleError, record_purchase, record_sale
from app.services.recommendation import (
    apply_decision,
    assess_stock_risk,
    generate_recommendation_run,
)


def _steady_history(db, owner, product, per_day: int, days: int = 80) -> None:
    """Give a product a clean, forecastable sales history."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    for offset in range(days):
        record_sale(
            db,
            user=owner,
            sale_date=start + timedelta(days=offset),
            items=[{"product_id": product.id, "quantity": per_day}],
            allow_negative_stock=True,
        )
    db.commit()


def _restock_to(db, owner, supplier, product, target: int, unit_cost: float) -> None:
    """Bring a product's shelf count up to exactly `target` units."""
    from app.services.inventory import current_stock

    deficit = target - current_stock(db, product.id)
    if deficit > 0:
        record_purchase(
            db,
            user=owner,
            supplier_id=supplier.id,
            date_received=date.today(),
            items=[
                {"product_id": product.id, "quantity_received": deficit, "unit_cost": unit_cost}
            ],
        )
        db.commit()


def _budget(db, owner, amount: float) -> Budget:
    budget = Budget(user_id=owner.id, period="Test period", amount_available=amount)
    db.add(budget)
    db.commit()
    return budget


# --------------------------------------------------------------------------
# Stockout-risk detection (spec 4.7)
# --------------------------------------------------------------------------
def test_at_risk_products_are_flagged_and_healthy_ones_are_not(db, owner, supplier, make_product):
    thin = make_product("Thin Stock", "THIN1", selling_price=100, default_unit_cost=60)
    plenty = make_product("Well Stocked", "PLENTY1", selling_price=100, default_unit_cost=60)

    _steady_history(db, owner, thin, per_day=5)
    _steady_history(db, owner, plenty, per_day=5)

    _restock_to(db, owner, supplier, thin, 10, 60.0)     # ~2 days of cover
    _restock_to(db, owner, supplier, plenty, 400, 60.0)  # months of cover

    from app.services.forecasting import generate_forecasts

    generate_forecasts(db, horizon_days=14)
    db.commit()

    rows = {r["name"]: r for r in assess_stock_risk(db, horizon_days=14, safety_margin_pct=0.20)}

    assert rows["Thin Stock"]["at_risk"] is True
    assert rows["Thin Stock"]["estimated_shortage"] > 0
    assert rows["Thin Stock"]["status"] == "Running low"

    assert rows["Well Stocked"]["at_risk"] is False
    assert rows["Well Stocked"]["estimated_shortage"] == 0
    assert rows["Well Stocked"]["status"] == "Stock is fine"


def test_products_without_enough_history_are_reported_not_forecast(db, owner, make_product):
    sparse = make_product("Barely Sold", "SPARSE1", opening_stock=5)
    record_sale(
        db, user=owner, sale_date=date.today(), items=[{"product_id": sparse.id, "quantity": 1}]
    )
    db.commit()

    from app.services.forecasting import generate_forecasts

    generate_forecasts(db, horizon_days=14)
    db.commit()

    row = next(r for r in assess_stock_risk(db, horizon_days=14) if r["name"] == "Barely Sold")
    assert row["at_risk"] is False
    assert row["status"] == "Not enough sales history"
    assert row["forecast_demand"] is None


# --------------------------------------------------------------------------
# Budget allocation (spec 4.8)
# --------------------------------------------------------------------------
def test_full_budget_covers_every_required_quantity(db, owner, supplier, make_product):
    a = make_product("Product A", "A1", selling_price=100, default_unit_cost=50)
    b = make_product("Product B", "B1", selling_price=100, default_unit_cost=50)
    for product in (a, b):
        _steady_history(db, owner, product, per_day=4)
        _restock_to(db, owner, supplier, product, 5, 50.0)

    budget = _budget(db, owner, 1_000_000.0)  # far more than enough
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    assert run.budget_constrained is False
    assert run.products_considered == 2
    for item in run.items:
        assert item.recommended_quantity == item.required_quantity
        assert item.recommended_cost == pytest.approx(item.required_cost)
    assert run.total_recommended_cost == pytest.approx(run.total_required_cost)


def test_shortfall_allocates_top_down_by_priority_rank(db, owner, supplier, make_product):
    """The core budget-constrained behaviour.

    ``urgent`` is nearly empty and sells fast; ``comfortable`` has a milder gap.
    With only enough money for one of them, the urgent one must be funded first.
    """
    urgent = make_product("Urgent Fast Mover", "URG1", selling_price=100, default_unit_cost=50)
    comfortable = make_product("Milder Gap", "MILD1", selling_price=100, default_unit_cost=50)

    _steady_history(db, owner, urgent, per_day=10)
    _steady_history(db, owner, comfortable, per_day=10)

    _restock_to(db, owner, supplier, urgent, 2, 50.0)     # essentially empty
    _restock_to(db, owner, supplier, comfortable, 120, 50.0)  # mostly covered

    budget = _budget(db, owner, 3000.0)  # deliberately far too little
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    assert run.budget_constrained is True

    by_name = {}
    for item in run.items:
        product = urgent if item.product_id == urgent.id else comfortable
        by_name[product.name] = item

    urgent_line = by_name["Urgent Fast Mover"]
    mild_line = by_name["Milder Gap"]

    # The emptier shelf ranks higher and gets funded first.
    assert urgent_line.priority_rank < mild_line.priority_rank
    assert urgent_line.stockout_risk_score > mild_line.stockout_risk_score
    assert urgent_line.recommended_quantity > 0
    assert mild_line.recommended_quantity == 0

    # Never overspend, and report the gap honestly.
    assert run.total_recommended_cost <= run.budget_amount + 1e-6
    assert run.total_required_cost > run.budget_amount


def test_allocation_never_exceeds_the_budget(db, owner, supplier, make_product):
    products = []
    for i in range(6):
        product = make_product(
            f"Item {i}", f"ITEM{i}", selling_price=100 + i * 10, default_unit_cost=40 + i * 5
        )
        _steady_history(db, owner, product, per_day=3 + i)
        _restock_to(db, owner, supplier, product, 3, 40.0 + i * 5)
        products.append(product)

    budget = _budget(db, owner, 5000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    spent = sum(item.recommended_cost for item in run.items)
    assert spent <= 5000.0 + 1e-6
    assert run.total_recommended_cost == pytest.approx(spent, abs=0.01)
    # Ranks are a clean 1..N with no gaps or duplicates.
    ranks = sorted(item.priority_rank for item in run.items)
    assert ranks == list(range(1, len(ranks) + 1))


def test_priority_score_uses_the_documented_weights(db, owner, supplier, make_product):
    from app.config import settings

    product = make_product("Weighted", "WGT1", selling_price=200, default_unit_cost=80)
    _steady_history(db, owner, product, per_day=6)
    _restock_to(db, owner, supplier, product, 5, 80.0)

    budget = _budget(db, owner, 50_000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    item = run.items[0]
    expected = (
        settings.weight_stockout_risk * item.stockout_risk_score
        + settings.weight_demand_velocity * item.demand_velocity_score
        + settings.weight_cost_efficiency * item.cost_efficiency_score
    )
    assert item.priority_score == pytest.approx(expected, abs=1e-3)

    # The weights themselves are persisted, so an old run stays explainable.
    weights = json.loads(run.weights_used)
    assert weights["stockout_risk"] == settings.weight_stockout_risk
    assert weights["demand_velocity"] == settings.weight_demand_velocity
    assert weights["cost_efficiency"] == settings.weight_cost_efficiency
    assert sum(weights.values()) == pytest.approx(1.0)


def test_insufficient_data_products_are_skipped_not_recommended(db, owner, supplier, make_product):
    good = make_product("Has History", "GOOD1", selling_price=100, default_unit_cost=50)
    sparse = make_product("No History", "NONE1", selling_price=100, default_unit_cost=50)

    _steady_history(db, owner, good, per_day=5)
    _restock_to(db, owner, supplier, good, 3, 50.0)
    _restock_to(db, owner, supplier, sparse, 1, 50.0)

    budget = _budget(db, owner, 100_000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    recommended_ids = {item.product_id for item in run.items}
    assert good.id in recommended_ids
    assert sparse.id not in recommended_ids
    assert run.products_skipped_no_forecast >= 1


def test_every_line_carries_its_reasoning(db, owner, supplier, make_product):
    """The operator must always be able to see *why* (spec 4.8)."""
    product = make_product("Explainable", "EXPL1", selling_price=150, default_unit_cost=90)
    _steady_history(db, owner, product, per_day=7)
    _restock_to(db, owner, supplier, product, 4, 90.0)

    budget = _budget(db, owner, 100_000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    item = run.items[0]
    assert item.reason and len(item.reason) > 40
    assert "Explainable" in item.reason
    # Each of the numbers the spec requires is stored on the row itself.
    assert item.current_stock is not None
    assert item.forecast_demand > 0
    assert item.estimated_shortage > 0
    assert item.unit_cost > 0
    assert item.recommended_quantity >= 0
    assert item.recommended_cost >= 0
    assert item.priority_rank >= 1
    assert item.forecast_id is not None


def test_safety_margin_increases_the_shortage(db, owner, supplier, make_product):
    product = make_product("Margin Test", "MRG1", selling_price=100, default_unit_cost=50)
    _steady_history(db, owner, product, per_day=6)
    _restock_to(db, owner, supplier, product, 30, 50.0)

    budget = _budget(db, owner, 500_000.0)

    lean = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.0
    )
    db.commit()
    generous = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.50
    )
    db.commit()

    assert generous.items[0].required_quantity > lean.items[0].required_quantity
    assert lean.items[0].safety_stock == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Operator decisions (spec 4.8: accept / modify / reject)
# --------------------------------------------------------------------------
def test_operator_can_accept_modify_and_reject(db, owner, supplier, make_product):
    products = []
    for i in range(3):
        product = make_product(f"Decide {i}", f"DEC{i}", selling_price=120, default_unit_cost=60)
        _steady_history(db, owner, product, per_day=4 + i)
        _restock_to(db, owner, supplier, product, 2, 60.0)
        products.append(product)

    budget = _budget(db, owner, 200_000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    items = sorted(run.items, key=lambda r: r.priority_rank)
    assert all(item.status == RecommendationStatus.proposed for item in items)

    accepted = apply_decision(
        db, recommendation_id=items[0].id, status=RecommendationStatus.accepted, quantity=None
    )
    modified = apply_decision(
        db, recommendation_id=items[1].id, status=RecommendationStatus.modified, quantity=7
    )
    rejected = apply_decision(
        db, recommendation_id=items[2].id, status=RecommendationStatus.rejected, quantity=None
    )
    db.commit()

    assert accepted.status == RecommendationStatus.accepted
    assert accepted.operator_quantity == accepted.recommended_quantity

    assert modified.status == RecommendationStatus.modified
    assert modified.operator_quantity == 7

    assert rejected.status == RecommendationStatus.rejected
    assert rejected.operator_quantity == 0

    for item in (accepted, modified, rejected):
        assert item.decided_at is not None


def test_modifying_without_a_quantity_is_rejected(db, owner, supplier, make_product):
    product = make_product("Needs Qty", "QTY1", selling_price=120, default_unit_cost=60)
    _steady_history(db, owner, product, per_day=5)
    _restock_to(db, owner, supplier, product, 2, 60.0)

    budget = _budget(db, owner, 100_000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    db.commit()

    with pytest.raises(BusinessRuleError, match="quantity"):
        apply_decision(
            db,
            recommendation_id=run.items[0].id,
            status=RecommendationStatus.modified,
            quantity=None,
        )


def test_recommendation_never_places_an_order(db, owner, supplier, make_product):
    """Decision support, not automation: accepting must not change stock."""
    from app.services.inventory import current_stock

    product = make_product("No Auto Order", "NOAUTO1", selling_price=120, default_unit_cost=60)
    _steady_history(db, owner, product, per_day=5)
    _restock_to(db, owner, supplier, product, 3, 60.0)

    stock_before = current_stock(db, product.id)
    budget = _budget(db, owner, 100_000.0)
    run = generate_recommendation_run(
        db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
    )
    apply_decision(
        db, recommendation_id=run.items[0].id, status=RecommendationStatus.accepted, quantity=None
    )
    db.commit()

    # Stock only moves when a real delivery is recorded, never from a recommendation.
    assert current_stock(db, product.id) == stock_before


def test_zero_budget_is_rejected_with_a_clear_message(db, owner):
    budget = Budget(user_id=owner.id, period="Empty", amount_available=0.0)
    db.add(budget)
    db.commit()

    with pytest.raises(BusinessRuleError, match="more than zero"):
        generate_recommendation_run(
            db, user=owner, budget_id=budget.id, horizon_days=14, safety_margin_pct=0.20
        )
