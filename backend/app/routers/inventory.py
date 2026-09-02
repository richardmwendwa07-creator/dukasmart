"""Inventory dashboard: derived stock levels + the movement audit trail."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import InventoryMovement, Product
from ..schemas import AdjustmentCreate, MovementOut, StockRow
from ..services.inventory import (
    BusinessRuleError,
    current_stock_map,
    latest_unit_costs,
    record_adjustment,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/stock", response_model=list[StockRow])
def stock_list(
    db: DbSession, _: CurrentUser, include_inactive: bool = Query(False)
) -> list[StockRow]:
    stmt = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    products = list(db.execute(stmt.order_by(Product.name)).scalars())
    ids = [p.id for p in products]
    stock = current_stock_map(db, ids)
    costs = latest_unit_costs(db, ids)

    rows = []
    for product in products:
        qty = stock.get(product.id, 0)
        unit_cost = float(costs.get(product.id) or product.default_unit_cost or 0.0)
        rows.append(
            StockRow(
                product_id=product.id,
                name=product.name,
                sku=product.sku,
                category=product.category,
                current_stock=qty,
                selling_price=float(product.selling_price),
                unit_cost=round(unit_cost, 2),
                stock_value_at_cost=round(qty * unit_cost, 2),
            )
        )
    return rows


@router.get("/movements", response_model=list[MovementOut])
def movements(
    db: DbSession,
    _: CurrentUser,
    product_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
) -> list[InventoryMovement]:
    stmt = select(InventoryMovement)
    if product_id is not None:
        stmt = stmt.where(InventoryMovement.product_id == product_id)
    return list(
        db.execute(
            stmt.order_by(InventoryMovement.timestamp.desc(), InventoryMovement.id.desc()).limit(limit)
        ).scalars()
    )


@router.post("/adjustments", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def create_adjustment(
    payload: AdjustmentCreate, db: DbSession, _: CurrentUser
) -> InventoryMovement:
    """Stock-take correction, breakage, or expiry write-off."""
    try:
        movement = record_adjustment(
            db,
            product_id=payload.product_id,
            change_qty=payload.change_qty,
            note=payload.note,
        )
        db.commit()
    except BusinessRuleError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return movement
