"""Sales and purchase recording. Both are atomic stock-changing operations."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, DbSession
from ..models import Purchase, PurchaseItem, Sale, SaleItem, Supplier
from ..schemas import PurchaseCreate, PurchaseOut, SaleCreate, SaleOut
from ..services.inventory import BusinessRuleError, record_purchase, record_sale

router = APIRouter(prefix="/api", tags=["transactions"])


# --------------------------------------------------------------------------
# Serialisation helpers (attach product/supplier names for the UI)
# --------------------------------------------------------------------------
def _sale_out(sale: Sale) -> SaleOut:
    out = SaleOut.model_validate(sale)
    by_id = {item.id: item for item in sale.items}
    for line in out.items:
        source = by_id[line.id]
        line.product_name = source.product.name if source.product else None
        line.line_total = round(line.quantity * line.unit_price_at_sale, 2)
    return out


def _purchase_out(purchase: Purchase) -> PurchaseOut:
    out = PurchaseOut.model_validate(purchase)
    out.supplier_name = purchase.supplier.name if purchase.supplier else None
    by_id = {item.id: item for item in purchase.items}
    for line in out.items:
        source = by_id[line.id]
        line.product_name = source.product.name if source.product else None
        line.line_total = round(line.quantity_received * line.unit_cost, 2)
    return out


# --------------------------------------------------------------------------
# Sales
# --------------------------------------------------------------------------
@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, db: DbSession, user: CurrentUser) -> SaleOut:
    sale_date = payload.date or date.today()
    if sale_date > date.today():
        raise HTTPException(status_code=400, detail="A sale cannot be dated in the future.")
    try:
        sale = record_sale(
            db,
            user=user,
            sale_date=sale_date,
            items=[i.model_dump() for i in payload.items],
            note=payload.note,
        )
        db.commit()
    except BusinessRuleError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    sale = db.execute(
        select(Sale)
        .options(selectinload(Sale.items).selectinload(SaleItem.product))
        .where(Sale.id == sale.id)
    ).scalar_one()
    return _sale_out(sale)


@router.get("/sales", response_model=list[SaleOut])
def list_sales(
    db: DbSession,
    _: CurrentUser,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[SaleOut]:
    stmt = select(Sale).options(selectinload(Sale.items).selectinload(SaleItem.product))
    if start:
        stmt = stmt.where(Sale.date >= start)
    if end:
        stmt = stmt.where(Sale.date <= end)
    sales = list(
        db.execute(stmt.order_by(Sale.date.desc(), Sale.id.desc()).limit(limit)).scalars()
    )
    return [_sale_out(s) for s in sales]


@router.get("/sales/{sale_id}", response_model=SaleOut)
def get_sale(sale_id: int, db: DbSession, _: CurrentUser) -> SaleOut:
    sale = db.execute(
        select(Sale)
        .options(selectinload(Sale.items).selectinload(SaleItem.product))
        .where(Sale.id == sale_id)
    ).scalar_one_or_none()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found.")
    return _sale_out(sale)


# --------------------------------------------------------------------------
# Purchases
# --------------------------------------------------------------------------
@router.post("/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(payload: PurchaseCreate, db: DbSession, user: CurrentUser) -> PurchaseOut:
    received = payload.date_received or date.today()
    if received > date.today():
        raise HTTPException(status_code=400, detail="A delivery cannot be dated in the future.")
    if db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status_code=400, detail="Supplier not found. Add the supplier first.")

    try:
        purchase = record_purchase(
            db,
            user=user,
            supplier_id=payload.supplier_id,
            date_received=received,
            items=[i.model_dump() for i in payload.items],
            note=payload.note,
        )
        db.commit()
    except BusinessRuleError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    purchase = db.execute(
        select(Purchase)
        .options(
            selectinload(Purchase.items).selectinload(PurchaseItem.product),
            selectinload(Purchase.supplier),
        )
        .where(Purchase.id == purchase.id)
    ).scalar_one()
    return _purchase_out(purchase)


@router.get("/purchases", response_model=list[PurchaseOut])
def list_purchases(
    db: DbSession,
    _: CurrentUser,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[PurchaseOut]:
    stmt = select(Purchase).options(
        selectinload(Purchase.items).selectinload(PurchaseItem.product),
        selectinload(Purchase.supplier),
    )
    if start:
        stmt = stmt.where(Purchase.date_received >= start)
    if end:
        stmt = stmt.where(Purchase.date_received <= end)
    purchases = list(
        db.execute(
            stmt.order_by(Purchase.date_received.desc(), Purchase.id.desc()).limit(limit)
        ).scalars()
    )
    return [_purchase_out(p) for p in purchases]
