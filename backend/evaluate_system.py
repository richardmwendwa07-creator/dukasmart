"""DukaSmart — standalone evaluation harness.

Produces real numbers for the final project report (Chapter 4):
  * forecast accuracy per product (MAE / RMSE / method chosen)
  * budget scenarios S1..S6 with timings
  * environment and package versions

Writes everything into  backend/eval_output/  as CSV + JSON.

Run from the backend/ directory with the venv active:

    python evaluate_system.py
"""
from __future__ import annotations

import csv
import json
import math
import os
import platform
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from app.database import SessionLocal
from app.models import (
    Budget,
    DataSufficiency,
    Forecast,
    Product,
    RecommendationRun,
    Sale,
    SaleItem,
    User,
)
from app.services.forecasting import generate_forecasts, latest_forecasts
from app.services.recommendation import (
    assess_stock_risk,
    generate_recommendation_run,
)

OUT = Path(__file__).parent / "eval_output"
OUT.mkdir(exist_ok=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _rmse(actuals, preds) -> float:
    if not actuals:
        return float("nan")
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actuals, preds)) / len(actuals))


def _mae(actuals, preds) -> float:
    if not actuals:
        return float("nan")
    return sum(abs(a - p) for a, p in zip(actuals, preds)) / len(actuals)


def _json_load(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


# --------------------------------------------------------------------------
# 1. Environment snapshot
# --------------------------------------------------------------------------
def environment() -> dict:
    import fastapi, sqlalchemy
    try:
        import sklearn
        sk = sklearn.__version__
    except Exception:
        sk = "not installed"
    try:
        import pandas
        pd = pandas.__version__
    except Exception:
        pd = "not installed"

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "fastapi": fastapi.__version__,
        "sqlalchemy": sqlalchemy.__version__,
        "scikit_learn": sk,
        "pandas": pd,
        "numpy": np.__version__,
        "generated_at": date.today().isoformat(),
    }


# --------------------------------------------------------------------------
# 2. Forecast accuracy  (uses whatever the system actually stored)
# --------------------------------------------------------------------------
def forecast_accuracy(db, horizon_days: int = 7) -> list[dict]:
    """Generate fresh forecasts, then read back the per-product metrics."""
    generate_forecasts(db, horizon_days=horizon_days, as_of=None)
    db.flush()

    rows: list[dict] = []
    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    for p in products:
        fc: Forecast | None = (
            db.query(Forecast)
            .filter(Forecast.product_id == p.id, Forecast.horizon_days == horizon_days)
            .order_by(Forecast.generated_at.desc(), Forecast.id.desc())
            .first()
        )
        if fc is None:
            rows.append({
                "product_id": p.id, "sku": p.sku, "name": p.name,
                "sufficiency": "none", "method_chosen": "",
"mae": "", "mape": "", "predicted": "",
                "wma_mae": "", "ses_mae": "", "gbm_mae": "",
            })
            continue

        scores = _json_load(fc.candidate_scores)
        rows.append({
            "product_id": p.id,
            "sku": p.sku,
            "name": p.name,
            "sufficiency": fc.data_sufficiency_flag.value,
            "method_chosen": fc.model_used or "",
            "mae": "" if fc.mae is None else round(float(fc.mae), 3),
            "mape": "" if fc.mape is None else round(float(fc.mape), 3),
            "predicted": "" if fc.predicted_quantity is None else round(float(fc.predicted_quantity), 2),
            "wma_mae": _pick(scores, "weighted_moving_average", "mae"),
            "ses_mae": _pick(scores, "simple_exponential_smoothing", "mae"),
            "gbm_mae": _pick(scores, "gradient_boosting", "mae"),
            "n_obs": fc.observations_used or 0,
        })
    return rows


def _pick(scores, model_name: str, metric: str):
    """candidate_scores is a list of {model, mae, mape, error} dicts."""
    if not isinstance(scores, list):
        return ""
    for row in scores:
        if isinstance(row, dict) and row.get("model") == model_name:
            return row.get(metric, "")
    return ""


# --------------------------------------------------------------------------
# 3. Budget scenarios S1..S6
# --------------------------------------------------------------------------
SCENARIOS = [
    ("S1", 500.0),
    ("S2", 1000.0),
    ("S3", 2000.0),
    ("S4", 5000.0),
    ("S5", 10000.0),
    ("S6", 20000.0),
]


def budget_scenarios(db, user: User, horizon_days: int = 7) -> list[dict]:
    rows: list[dict] = []
    for name, amount in SCENARIOS:
        # Create a fresh budget row so the run has something to attach to
        b = Budget(user_id=user.id, period=f"eval-{name}", amount_available=amount)
        db.add(b)
        db.flush()

        t0 = time.perf_counter()
        try:
            run: RecommendationRun = generate_recommendation_run(
                db,
                user=user,
                budget_id=b.id,
                horizon_days=horizon_days,
                safety_margin_pct=0.15,
                refresh_forecasts=False,
            )
            elapsed = time.perf_counter() - t0
            db.flush()
            rows.append({
                "scenario": name,
                "budget": amount,
                "constrained": run.budget_constrained,
                "products_considered": run.products_considered,
                "total_required_cost": round(run.total_required_cost, 2),
                "total_recommended_cost": round(run.total_recommended_cost, 2),
                "items_fully_funded": sum(
                    1 for r in run.items if r.recommended_quantity >= r.required_quantity
                ),
                "items_partially_funded": sum(
                    1 for r in run.items if 0 < r.recommended_quantity < r.required_quantity
                ),
                "items_unfunded": sum(1 for r in run.items if r.recommended_quantity == 0),
                "runtime_seconds": round(elapsed, 4),
            })
        except Exception as e:
            rows.append({
                "scenario": name, "budget": amount, "error": repr(e),
                "runtime_seconds": round(time.perf_counter() - t0, 4),
            })
    return rows


# --------------------------------------------------------------------------
# 4. Stock-risk snapshot (uses real sales history)
# --------------------------------------------------------------------------
def stock_risk_snapshot(db, horizon_days: int = 7) -> list[dict]:
    rows = assess_stock_risk(db, horizon_days=horizon_days)
    return [
        {
            "product_id": r["product_id"], "name": r["name"], "sku": r["sku"],
            "current_stock": r["current_stock"],
            "forecast_demand": r["forecast_demand"],
            "estimated_shortage": r["estimated_shortage"],
            "at_risk": r["at_risk"],
            "status": r["status"],
            "model_used": r["model_used"],
        }
        for r in rows
    ]


# --------------------------------------------------------------------------
# 5. Data summary (how much real data is in the DB)
# --------------------------------------------------------------------------
def data_summary(db) -> dict:
    return {
        "users": db.query(User).count(),
        "products": db.query(Product).count(),
        "active_products": db.query(Product).filter(Product.is_active.is_(True)).count(),
        "sales": db.query(Sale).count(),
        "sale_items": db.query(SaleItem).count(),
        "forecasts": db.query(Forecast).count(),
        "recommendation_runs": db.query(RecommendationRun).count(),
    }


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------
def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("(no rows)\n", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> int:
    db = SessionLocal()
    try:
        env = environment()
        (OUT / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")

        user = db.query(User).first()
        if user is None:
            print("ERROR: no user in the database. Run seed.py first.")
            return 2

        summary = data_summary(db)
        (OUT / "data_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print("[1/4] Forecast accuracy ...")
        fa = forecast_accuracy(db, horizon_days=90)
        write_csv(OUT / "forecast_accuracy.csv", fa)

        print("[2/4] Stock risk snapshot ...")
        sr = stock_risk_snapshot(db, horizon_days=90)
        write_csv(OUT / "stock_risk.csv", sr)

        print("[3/4] Budget scenarios S1..S6 ...")
        bs = budget_scenarios(db, user, horizon_days=90)
        write_csv(OUT / "budget_scenarios.csv", bs)

        print("[4/4] Summary ...")
        summary_all = {
            "environment": env,
            "data_summary": summary,
            "forecast_products": len(fa),
            "forecast_with_metrics": sum(1 for r in fa if r["mae"] != ""),
            "at_risk_products": sum(1 for r in sr if r["at_risk"]),
            "budget_scenarios": len(bs),
        }
        (OUT / "summary.json").write_text(
            json.dumps(summary_all, indent=2), encoding="utf-8"
        )

        db.commit()
        print(f"\nDone. Files written to: {OUT}")
        for p in sorted(OUT.glob("*")):
            print(f"  {p.name}  ({p.stat().st_size} bytes)")
        return 0

    except Exception:
        db.rollback()
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
