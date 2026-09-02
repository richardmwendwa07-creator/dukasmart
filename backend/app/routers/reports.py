"""Reporting: sales, purchases, stock, forecast accuracy, and follow-through."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession, OwnerUser
from ..models import (
    DataSufficiency,
    Forecast,
    Product,
    Purchase,
    PurchaseItem,
    Recommendation,
    RecommendationRun,
    Sale,
    SaleItem,
    Supplier,
)
from ..schemas import (
    ForecastAccuracyReport,
    ForecastAccuracyRow,
    PurchasesReport,
    PurchasesReportRow,
    RecommendationFollowThroughRow,
    SalesReport,
    SalesReportRow,
)
from ..services.forecasting import forecast_window
from ..services.inventory import latest_unit_costs

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _default_range(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or date.today()
    start = start or (end - timedelta(days=29))
    return start, end


@router.get("/sales", response_model=SalesReport)
def sales_report(
    db: DbSession,
    _: CurrentUser,
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> SalesReport:
    start, end = _default_range(start, end)

    rows = db.execute(
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.default_unit_cost,
            func.sum(SaleItem.quantity),
            func.sum(SaleItem.quantity * SaleItem.unit_price_at_sale),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.date >= start, Sale.date <= end)
        .group_by(Product.id, Product.name, Product.sku, Product.default_unit_cost)
    ).all()

    # Cost basis: the most recently paid purchase price per unit, same rule the
    # restock planner uses (services.inventory.latest_unit_costs), so profit
    # here and cost-efficiency there agree with each other. Products never
    # actually purchased fall back to the product's listed purchase cost.
    latest_costs = latest_unit_costs(db, [int(pid) for pid, *_ in rows])

    by_product = []
    for pid, name, sku, default_cost, units, revenue in rows:
        units = int(units or 0)
        revenue = round(float(revenue or 0), 2)
        unit_cost = float(latest_costs.get(int(pid)) or default_cost or 0.0)
        cost_of_goods_sold = round(unit_cost * units, 2)
        profit = round(revenue - cost_of_goods_sold, 2)
        by_product.append(
            SalesReportRow(
                product_id=int(pid),
                name=name,
                sku=sku,
                units_sold=units,
                revenue=revenue,
                unit_cost=round(unit_cost, 2),
                cost_of_goods_sold=cost_of_goods_sold,
                profit=profit,
                margin_pct=round(profit / revenue * 100, 1) if revenue > 0 else None,
            )
        )
    # Most profitable first — that's the ordering useful for restocking decisions.
    by_product.sort(key=lambda r: r.profit, reverse=True)

    daily = db.execute(
        select(Sale.date, func.sum(Sale.total_amount), func.count(Sale.id))
        .where(Sale.date >= start, Sale.date <= end)
        .group_by(Sale.date)
        .order_by(Sale.date)
    ).all()

    sale_count = db.execute(
        select(func.count(Sale.id)).where(Sale.date >= start, Sale.date <= end)
    ).scalar_one()

    total_revenue = round(sum(r.revenue for r in by_product), 2)
    total_cogs = round(sum(r.cost_of_goods_sold for r in by_product), 2)
    total_profit = round(sum(r.profit for r in by_product), 2)

    return SalesReport(
        start=start,
        end=end,
        total_revenue=total_revenue,
        total_units=sum(r.units_sold for r in by_product),
        sale_count=int(sale_count or 0),
        total_cost_of_goods_sold=total_cogs,
        total_profit=total_profit,
        overall_margin_pct=(
            round(total_profit / total_revenue * 100, 1) if total_revenue > 0 else None
        ),
        by_product=by_product,
        by_day=[
            {
                "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                "revenue": round(float(total or 0), 2),
                "sales": int(count or 0),
            }
            for d, total, count in daily
        ],
    )


@router.get("/purchases", response_model=PurchasesReport)
def purchases_report(
    db: DbSession,
    _: CurrentUser,
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> PurchasesReport:
    start, end = _default_range(start, end)

    rows = db.execute(
        select(
            Product.id,
            Product.name,
            Product.sku,
            func.sum(PurchaseItem.quantity_received),
            func.sum(PurchaseItem.quantity_received * PurchaseItem.unit_cost),
        )
        .join(PurchaseItem, PurchaseItem.product_id == Product.id)
        .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
        .where(Purchase.date_received >= start, Purchase.date_received <= end)
        .group_by(Product.id, Product.name, Product.sku)
        .order_by(func.sum(PurchaseItem.quantity_received * PurchaseItem.unit_cost).desc())
    ).all()

    by_product = [
        PurchasesReportRow(
            product_id=int(pid),
            name=name,
            sku=sku,
            units_received=int(units or 0),
            spend=round(float(spend or 0), 2),
        )
        for pid, name, sku, units, spend in rows
    ]

    supplier_rows = db.execute(
        select(Supplier.name, func.sum(Purchase.total_cost), func.count(Purchase.id))
        .join(Purchase, Purchase.supplier_id == Supplier.id)
        .where(Purchase.date_received >= start, Purchase.date_received <= end)
        .group_by(Supplier.name)
        .order_by(func.sum(Purchase.total_cost).desc())
    ).all()

    purchase_count = db.execute(
        select(func.count(Purchase.id)).where(
            Purchase.date_received >= start, Purchase.date_received <= end
        )
    ).scalar_one()

    return PurchasesReport(
        start=start,
        end=end,
        total_spend=round(sum(r.spend for r in by_product), 2),
        total_units=sum(r.units_received for r in by_product),
        purchase_count=int(purchase_count or 0),
        by_product=by_product,
        by_supplier=[
            {"supplier": name, "spend": round(float(spend or 0), 2), "deliveries": int(count or 0)}
            for name, spend, count in supplier_rows
        ],
    )


@router.get("/forecast-accuracy", response_model=ForecastAccuracyReport)
def forecast_accuracy(
    db: DbSession, _: CurrentUser, limit: int = Query(200, ge=1, le=1000)
) -> ForecastAccuracyReport:
    """Predicted vs. actual, for forecasts whose horizon has already elapsed.

    A forecast made today covering the next 14 days cannot be scored yet; those
    are reported as ``pending_count`` rather than being scored against partial data.
    """
    forecasts = list(
        db.execute(
            select(Forecast)
            .where(Forecast.data_sufficiency_flag == DataSufficiency.sufficient)
            .order_by(Forecast.generated_at.desc())
            .limit(limit)
        ).scalars()
    )
    if not forecasts:
        return ForecastAccuracyReport(rows=[], mae=None, mape=None, evaluated_count=0, pending_count=0)

    names = {p.id: p.name for p in db.execute(select(Product)).scalars()}
    today = date.today()

    # One query for all the actuals we might need.
    actual_rows = db.execute(
        select(SaleItem.product_id, Sale.date, func.sum(SaleItem.quantity))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .group_by(SaleItem.product_id, Sale.date)
    ).all()
    actuals: dict[int, dict[date, int]] = defaultdict(dict)
    for pid, day, qty in actual_rows:
        parsed = day if isinstance(day, date) else date.fromisoformat(str(day))
        actuals[int(pid)][parsed] = int(qty or 0)

    rows: list[ForecastAccuracyRow] = []
    pending = 0
    for forecast in forecasts:
        window_start, window_end = forecast_window(forecast)
        if window_end > today:
            pending += 1
            continue

        product_actuals = actuals.get(forecast.product_id, {})
        actual_total = sum(
            qty for day, qty in product_actuals.items() if window_start <= day <= window_end
        )
        predicted = float(forecast.predicted_quantity or 0.0)
        abs_error = abs(predicted - actual_total)
        pct_error = (abs_error / actual_total * 100.0) if actual_total > 0 else None

        rows.append(
            ForecastAccuracyRow(
                forecast_id=forecast.id,
                product_id=forecast.product_id,
                product_name=names.get(forecast.product_id, "Unknown"),
                generated_at=forecast.generated_at,
                horizon_days=forecast.horizon_days,
                model_used=forecast.model_used,
                predicted_quantity=round(predicted, 2),
                actual_quantity=actual_total,
                absolute_error=round(abs_error, 2),
                percentage_error=None if pct_error is None else round(pct_error, 1),
                window_start=window_start,
                window_end=window_end,
                evaluable=True,
            )
        )

    mae = round(sum(r.absolute_error for r in rows) / len(rows), 2) if rows else None
    scorable = [r.percentage_error for r in rows if r.percentage_error is not None]
    mape = round(sum(scorable) / len(scorable), 1) if scorable else None

    return ForecastAccuracyReport(
        rows=rows, mae=mae, mape=mape, evaluated_count=len(rows), pending_count=pending
    )


@router.get("/recommendation-follow-through", response_model=list[RecommendationFollowThroughRow])
def recommendation_follow_through(
    db: DbSession, _: OwnerUser, limit: int = Query(200, ge=1, le=1000)
) -> list[RecommendationFollowThroughRow]:
    """What was recommended vs. what the shop actually bought afterwards.

    'Actually purchased' counts deliveries of that product recorded on or after
    the run date, which is the closest honest link available without asking the
    operator to tag each delivery to a recommendation.
    """
    recs = list(
        db.execute(
            select(Recommendation)
            .join(RecommendationRun, RecommendationRun.id == Recommendation.run_id)
            .order_by(Recommendation.run_id.desc(), Recommendation.priority_rank)
            .limit(limit)
        ).scalars()
    )
    if not recs:
        return []

    runs = {
        r.id: r
        for r in db.execute(
            select(RecommendationRun).where(
                RecommendationRun.id.in_({rec.run_id for rec in recs})
            )
        ).scalars()
    }
    names = {p.id: p.name for p in db.execute(select(Product)).scalars()}

    purchase_rows = db.execute(
        select(
            PurchaseItem.product_id,
            Purchase.date_received,
            PurchaseItem.quantity_received,
            PurchaseItem.unit_cost,
        ).join(Purchase, Purchase.id == PurchaseItem.purchase_id)
    ).all()

    out: list[RecommendationFollowThroughRow] = []
    for rec in recs:
        run = runs.get(rec.run_id)
        run_date = run.generated_at.date() if run else date.today()
        bought_qty = 0
        bought_cost = 0.0
        for pid, received, qty, cost in purchase_rows:
            parsed = received if isinstance(received, date) else date.fromisoformat(str(received))
            if int(pid) == rec.product_id and parsed >= run_date:
                bought_qty += int(qty or 0)
                bought_cost += float(qty or 0) * float(cost or 0)

        out.append(
            RecommendationFollowThroughRow(
                run_id=rec.run_id,
                generated_at=run.generated_at if run else rec.generated_at,
                product_id=rec.product_id,
                product_name=names.get(rec.product_id, "Unknown"),
                recommended_quantity=rec.recommended_quantity,
                recommended_cost=float(rec.recommended_cost),
                status=rec.status,
                operator_quantity=rec.operator_quantity,
                actually_purchased_quantity=bought_qty,
                actually_purchased_cost=round(bought_cost, 2),
            )
        )
    return out
