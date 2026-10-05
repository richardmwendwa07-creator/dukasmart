"""DukaSmart API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from .config import settings
from .database import init_db
from .deps import CurrentUser, DbSession
from .models import DataSufficiency, Forecast, Product, Purchase, Sale, SaleItem, Supplier
from .routers import auth, catalog, forecasts, inventory, planning, reports, transactions
from .services.forecasting import latest_forecasts
from .services.inventory import current_stock_map
from .services.recommendation import assess_stock_risk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("dukasmart")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Auto-seed demo data on first startup. The seed script is idempotent:
    # it checks for existing users and skips if the database is already
    # populated. This ensures a fresh Render container (whose SQLite file
    # is discarded on each restart) always comes back with demo data.
    from .database import SessionLocal
    from .models import User
    _db = SessionLocal()
    try:
        if _db.query(User).count() == 0:
            logger.info("Database is empty - running seed script")
            try:
                from seed import seed as run_seed
                run_seed()
                logger.info("Seed completed successfully")
            except Exception as exc:
                logger.error("Auto-seed failed: %s", exc)
    finally:
        _db.close()

    logger.info("DukaSmart API ready (database: %s)", settings.database_url.split("///")[-1])
    yield


app = FastAPI(
    title="DukaSmart API",
    version="1.0.0",
    description=(
        "Budget-aware demand forecasting and inventory decision support for small "
        "retail shops. Decision support only - the system never places orders."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Auth is a Bearer token, not a cookie, so no origin needs credentialed
    # requests — that's what lets allow_origins be "*" for local/dev use.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn Pydantic's field-path errors into one plain sentence per problem.

    Note: we deliberately do NOT echo the submitted value back, so a mistyped
    password can never end up in an error body or a log line.
    """
    messages = []
    for error in exc.errors():
        location = " -> ".join(str(p) for p in error["loc"] if p not in ("body", "query"))
        message = error.get("msg", "Invalid value")
        message = message.replace("Value error, ", "")
        messages.append(f"{location}: {message}" if location else message)
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


# --------------------------------------------------------------------------
# Dashboard summary (one call for the home screen)
# --------------------------------------------------------------------------
summary_router = APIRouter(prefix="/api", tags=["dashboard"])


@summary_router.get("/summary")
def dashboard_summary(
    db: DbSession, _: CurrentUser, horizon_days: int = settings.default_horizon_days
) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=6)
    prev_week_start = today - timedelta(days=13)

    def revenue_between(start: date, end: date) -> float:
        value = db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0.0)).where(
                Sale.date >= start, Sale.date <= end
            )
        ).scalar_one()
        return round(float(value or 0), 2)

    this_week = revenue_between(week_ago, today)
    last_week = revenue_between(prev_week_start, week_ago - timedelta(days=1))

    products = list(db.execute(select(Product).where(Product.is_active.is_(True))).scalars())
    stock = current_stock_map(db, [p.id for p in products])
    out_of_stock = sum(1 for p in products if stock.get(p.id, 0) <= 0)

    risk_rows = assess_stock_risk(db, horizon_days=horizon_days)
    at_risk = [r for r in risk_rows if r["at_risk"]]

    forecast_map = latest_forecasts(db, horizon_days=horizon_days)
    insufficient = sum(
        1
        for f in forecast_map.values()
        if f.data_sufficiency_flag == DataSufficiency.insufficient_data
    )

    daily = db.execute(
        select(Sale.date, func.sum(Sale.total_amount))
        .where(Sale.date >= today - timedelta(days=29))
        .group_by(Sale.date)
        .order_by(Sale.date)
    ).all()

    top_sellers = db.execute(
        select(Product.name, func.sum(SaleItem.quantity))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.date >= week_ago)
        .group_by(Product.name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(5)
    ).all()

    return {
        "today": today.isoformat(),
        "horizon_days": horizon_days,
        "product_count": len(products),
        "supplier_count": db.execute(select(func.count(Supplier.id))).scalar_one(),
        "sale_count": db.execute(select(func.count(Sale.id))).scalar_one(),
        "purchase_count": db.execute(select(func.count(Purchase.id))).scalar_one(),
        "revenue_last_7_days": this_week,
        "revenue_previous_7_days": last_week,
        "revenue_change_pct": (
            round((this_week - last_week) / last_week * 100, 1) if last_week > 0 else None
        ),
        "stock_value_at_cost": None,  # filled by the inventory screen; kept out of the hot path
        "out_of_stock_count": out_of_stock,
        "running_low_count": len(at_risk),
        "insufficient_history_count": insufficient,
        "forecasts_available": len(forecast_map),
        "revenue_by_day": [
            {"date": d.isoformat() if hasattr(d, "isoformat") else str(d), "revenue": round(float(v or 0), 2)}
            for d, v in daily
        ],
        "top_sellers": [{"name": n, "units": int(q or 0)} for n, q in top_sellers],
        "running_low": at_risk[:6],
    }


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(transactions.router)
app.include_router(inventory.router)
app.include_router(forecasts.router)
app.include_router(planning.router)
app.include_router(reports.router)
app.include_router(summary_router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


# --------------------------------------------------------------------------
# Serve the built frontend, if it has been built (single-process deployment).
# In development the Vite dev server on :5173 proxies /api here instead.
# --------------------------------------------------------------------------
_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
