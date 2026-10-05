"""Budgets and budget-aware purchase recommendations (owner-only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import DbSession, OwnerUser
from ..models import Budget, Product, Recommendation, RecommendationRun
from ..schemas import (
    BudgetCreate,
    BudgetOut,
    RecommendationDecision,
    RecommendationOut,
    RecommendationRunOut,
    RecommendationRunRequest,
)
from ..services.inventory import BusinessRuleError
from ..services.recommendation import apply_decision, generate_recommendation_run

router = APIRouter(prefix="/api", tags=["planning"])


# --------------------------------------------------------------------------
# Budgets
# --------------------------------------------------------------------------
@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(db: DbSession, _: OwnerUser) -> list[Budget]:
    return list(db.execute(select(Budget).order_by(Budget.created_at.desc())).scalars())


@router.post("/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(payload: BudgetCreate, db: DbSession, user: OwnerUser) -> Budget:
    budget = Budget(
        user_id=user.id,
        period=payload.period.strip(),
        amount_available=payload.amount_available,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


# --------------------------------------------------------------------------
# Recommendation runs
# --------------------------------------------------------------------------
def _run_out(db, run: RecommendationRun) -> RecommendationRunOut:
    # `weights_used` is decoded by RecommendationRunOut's own validator.
    out = RecommendationRunOut.model_validate(run)
    out.budget_period = run.budget.period if run.budget else None
    out.budget_shortfall = round(
        max(0.0, float(run.total_required_cost) - float(run.total_recommended_cost)), 2
    )
    out.budget_remaining = round(
        max(0.0, float(run.budget_amount) - float(run.total_recommended_cost)), 2
    )

    products = {
        p.id: p
        for p in db.execute(
            select(Product)
            .options(selectinload(Product.preferred_supplier))
            .where(Product.id.in_([i.product_id for i in run.items] or [0]))
        ).scalars()
    }

    items = []
    for rec in sorted(run.items, key=lambda r: r.priority_rank):
        line = RecommendationOut.model_validate(rec)
        product = products.get(rec.product_id)
        if product is not None:
            line.product_name = product.name
            line.sku = product.sku
            line.supplier_name = (
                product.preferred_supplier.name if product.preferred_supplier else None
            )
        line.unfunded_quantity = max(0, rec.required_quantity - rec.recommended_quantity)
        line.unfunded_cost = round(line.unfunded_quantity * float(rec.unit_cost), 2)
        items.append(line)
    out.items = items

    # --- NEW: total expected gross profit of the recommended basket.
    # Derived from persisted columns (gross_profit_per_unit x
    # recommended_quantity, summed across every line) rather than trusting
    # any value already on `run` - this way it's correct whether `run` was
    # just generated or is being re-fetched later (list_runs, latest_run,
    # get_run all go through this same function). `gross_profit_per_unit`
    # is nullable (recommendations created before this feature existed won't
    # have it), so those lines simply contribute 0 rather than erroring.
    out.total_expected_gross_profit = round(
        sum((rec.gross_profit_per_unit or 0) * rec.recommended_quantity for rec in run.items), 2
    )
    # --- end new ---

    return out


def _load_run(db, run_id: int) -> RecommendationRun:
    run = db.execute(
        select(RecommendationRun)
        .options(selectinload(RecommendationRun.items), selectinload(RecommendationRun.budget))
        .where(RecommendationRun.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="That recommendation run was not found.")
    return run


@router.post("/recommendations/run", response_model=RecommendationRunOut)
def run_recommendations(
    payload: RecommendationRunRequest, db: DbSession, user: OwnerUser
) -> RecommendationRunOut:
    try:
        run = generate_recommendation_run(
            db,
            user=user,
            budget_id=payload.budget_id,
            horizon_days=payload.horizon_days,
            safety_margin_pct=payload.safety_margin_pct,
            refresh_forecasts=payload.refresh_forecasts,
        )
        db.commit()
    except BusinessRuleError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return _run_out(db, _load_run(db, run.id))


@router.get("/recommendations/runs", response_model=list[RecommendationRunOut])
def list_runs(
    db: DbSession, _: OwnerUser, limit: int = Query(20, ge=1, le=200)
) -> list[RecommendationRunOut]:
    runs = list(
        db.execute(
            select(RecommendationRun)
            .options(selectinload(RecommendationRun.items), selectinload(RecommendationRun.budget))
            .order_by(RecommendationRun.generated_at.desc(), RecommendationRun.id.desc())
            .limit(limit)
        ).scalars()
    )
    return [_run_out(db, r) for r in runs]


@router.get("/recommendations/runs/latest", response_model=RecommendationRunOut | None)
def latest_run(db: DbSession, _: OwnerUser) -> RecommendationRunOut | None:
    run = db.execute(
        select(RecommendationRun)
        .options(selectinload(RecommendationRun.items), selectinload(RecommendationRun.budget))
        .order_by(RecommendationRun.generated_at.desc(), RecommendationRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return _run_out(db, run) if run else None


@router.get("/recommendations/runs/{run_id}", response_model=RecommendationRunOut)
def get_run(run_id: int, db: DbSession, _: OwnerUser) -> RecommendationRunOut:
    return _run_out(db, _load_run(db, run_id))


@router.patch("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def decide(
    recommendation_id: int, payload: RecommendationDecision, db: DbSession, _: OwnerUser
) -> RecommendationOut:
    """Accept / modify / reject one line. This is the human-in-the-loop step:
    the system never acts on a recommendation itself."""
    try:
        rec = apply_decision(
            db,
            recommendation_id=recommendation_id,
            status=payload.status,
            quantity=payload.quantity,
        )
        db.commit()
    except BusinessRuleError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    out = RecommendationOut.model_validate(rec)
    product = db.get(Product, rec.product_id)
    if product is not None:
        out.product_name = product.name
        out.sku = product.sku
    out.unfunded_quantity = max(0, rec.required_quantity - rec.recommended_quantity)
    out.unfunded_cost = round(out.unfunded_quantity * float(rec.unit_cost), 2)
    return out


@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    db: DbSession, _: OwnerUser, run_id: int | None = Query(None)
) -> list[RecommendationOut]:
    stmt = select(Recommendation)
    if run_id is not None:
        stmt = stmt.where(Recommendation.run_id == run_id)
    recs = list(
        db.execute(stmt.order_by(Recommendation.run_id.desc(), Recommendation.priority_rank)).scalars()
    )
    products = {p.id: p for p in db.execute(select(Product)).scalars()}
    out = []
    for rec in recs:
        line = RecommendationOut.model_validate(rec)
        product = products.get(rec.product_id)
        if product:
            line.product_name = product.name
            line.sku = product.sku
        line.unfunded_quantity = max(0, rec.required_quantity - rec.recommended_quantity)
        line.unfunded_cost = round(line.unfunded_quantity * float(rec.unit_cost), 2)
        out.append(line)
    return out
