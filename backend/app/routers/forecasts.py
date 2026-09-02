"""Forecast generation, retrieval, and stockout-risk ("running low") detection."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..config import settings
from ..deps import CurrentUser, DbSession, OwnerUser
from ..models import Forecast, Product
from ..schemas import ForecastOut, ForecastRunRequest, StockRiskRow
from ..services.forecasting import build_daily_series, generate_forecasts, latest_forecasts
from ..services.recommendation import assess_stock_risk

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


def _to_out(forecast: Forecast, product_name: str | None = None) -> ForecastOut:
    # The JSON-text columns are decoded by ForecastOut's own validator.
    out = ForecastOut.model_validate(forecast)
    out.product_name = product_name or (forecast.product.name if forecast.product else None)
    return out


@router.get("/config")
def forecast_config(_: CurrentUser) -> dict:
    """Surface the tunables so the UI can explain itself without hardcoding."""
    return {
        "allowed_horizons": settings.allowed_horizon_list,
        "default_horizon_days": settings.default_horizon_days,
        "min_nonzero_observations": settings.min_nonzero_observations,
        "min_history_days": settings.min_history_days,
        "holdout_days": settings.holdout_days,
        "default_safety_margin_pct": settings.default_safety_margin_pct,
        "priority_weights": {
            "stockout_risk": settings.weight_stockout_risk,
            "demand_velocity": settings.weight_demand_velocity,
            "cost_efficiency": settings.weight_cost_efficiency,
        },
    }


@router.post("/run", response_model=list[ForecastOut])
def run_forecasts(payload: ForecastRunRequest, db: DbSession, _: OwnerUser) -> list[ForecastOut]:
    try:
        forecasts = generate_forecasts(
            db, horizon_days=payload.horizon_days, product_ids=payload.product_ids
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    names = {
        p.id: p.name for p in db.execute(select(Product)).scalars()
    }
    return [_to_out(f, names.get(f.product_id)) for f in forecasts]


@router.get("/latest", response_model=list[ForecastOut])
def latest(
    db: DbSession,
    _: CurrentUser,
    horizon_days: int | None = Query(None, ge=1, le=90),
) -> list[ForecastOut]:
    forecasts = latest_forecasts(db, horizon_days=horizon_days)
    names = {p.id: p.name for p in db.execute(select(Product)).scalars()}
    rows = [_to_out(f, names.get(f.product_id)) for f in forecasts.values()]
    rows.sort(key=lambda r: (r.product_name or "").lower())
    return rows


@router.get("/risk", response_model=list[StockRiskRow])
def stock_risk(
    db: DbSession,
    _: CurrentUser,
    horizon_days: int = Query(settings.default_horizon_days, ge=1, le=90),
    safety_margin_pct: float = Query(settings.default_safety_margin_pct, ge=0, le=2),
) -> list[StockRiskRow]:
    rows = assess_stock_risk(
        db, horizon_days=horizon_days, safety_margin_pct=safety_margin_pct
    )
    return [StockRiskRow(**r) for r in rows]


@router.get("/product/{product_id}")
def product_forecast_detail(
    product_id: int,
    db: DbSession,
    _: CurrentUser,
    horizon_days: int | None = Query(None, ge=1, le=90),
) -> dict:
    """History + forecast for one product, ready to plot."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    series = build_daily_series(db, product_id)
    history = [
        {"date": idx.date().isoformat(), "quantity": float(value)}
        for idx, value in series.items()
    ]

    forecast = latest_forecasts(db, horizon_days=horizon_days, product_ids=[product_id]).get(
        product_id
    )
    projected: list[dict] = []
    if forecast and forecast.model_params:
        params = json.loads(forecast.model_params)
        daily = params.get("daily_predictions") or []
        if history:
            import datetime as _dt

            last = _dt.date.fromisoformat(history[-1]["date"])
            projected = [
                {
                    "date": (last + _dt.timedelta(days=i + 1)).isoformat(),
                    "quantity": round(float(v), 2),
                }
                for i, v in enumerate(daily)
            ]

    return {
        "product": {"id": product.id, "name": product.name, "sku": product.sku},
        "history": history,
        "projected": projected,
        "forecast": _to_out(forecast, product.name).model_dump() if forecast else None,
    }
