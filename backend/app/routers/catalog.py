"""Products and suppliers CRUD."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, DbSession, OwnerUser
from ..models import Product, PurchaseItem, SaleItem, Supplier
from ..schemas import (
    ProductCreate,
    ProductOut,
    ProductUpdate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from ..services.inventory import current_stock_map, set_opening_stock

router = APIRouter(prefix="/api", tags=["catalog"])


# --------------------------------------------------------------------------
# Suppliers
# --------------------------------------------------------------------------
@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: DbSession, _: CurrentUser) -> list[Supplier]:
    return list(db.execute(select(Supplier).order_by(Supplier.name)).scalars())


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: DbSession, _: OwnerUser) -> Supplier:
    name = payload.name.strip()
    clash = db.execute(
        select(Supplier).where(func.lower(Supplier.name) == name.lower())
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A supplier called '{name}' already exists.",
        )
    supplier = Supplier(name=name, contact=payload.contact, notes=payload.notes)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int, payload: SupplierUpdate, db: DbSession, _: OwnerUser
) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
    for field, value in data.items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: int, db: DbSession, _: OwnerUser) -> None:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    if supplier.purchases:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"'{supplier.name}' has deliveries recorded against it, so it cannot be deleted. "
                "The purchase history must stay intact."
            ),
        )
    db.delete(supplier)
    db.commit()


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
def _to_out(product: Product, stock: int) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.current_stock = stock
    return out


def _resolve_suppliers(db, supplier_ids: list[int]) -> list[Supplier]:
    if not supplier_ids:
        return []
    suppliers = list(
        db.execute(select(Supplier).where(Supplier.id.in_(supplier_ids))).scalars()
    )
    found = {s.id for s in suppliers}
    missing = [i for i in supplier_ids if i not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Supplier(s) not found: {', '.join(str(m) for m in missing)}.",
        )
    return suppliers


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: DbSession,
    _: CurrentUser,
    include_inactive: bool = Query(False),
    search: str | None = Query(None),
) -> list[ProductOut]:
    stmt = select(Product).options(selectinload(Product.suppliers))
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(Product.name).like(pattern) | func.lower(Product.sku).like(pattern)
        )
    products = list(db.execute(stmt.order_by(Product.name)).scalars())
    stock = current_stock_map(db, [p.id for p in products])
    return [_to_out(p, stock.get(p.id, 0)) for p in products]


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession, _: CurrentUser) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _to_out(product, current_stock_map(db, [product_id]).get(product_id, 0))


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: DbSession, _: OwnerUser) -> ProductOut:
    clash = db.execute(select(Product).where(Product.sku == payload.sku)).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product code '{payload.sku}' is already used by '{clash.name}'.",
        )

    supplier_ids = list(payload.supplier_ids)
    if payload.preferred_supplier_id and payload.preferred_supplier_id not in supplier_ids:
        supplier_ids.append(payload.preferred_supplier_id)
    suppliers = _resolve_suppliers(db, supplier_ids)

    product = Product(
        name=payload.name.strip(),
        sku=payload.sku,
        category=(payload.category or "").strip() or None,
        selling_price=payload.selling_price,
        default_unit_cost=payload.default_unit_cost,
        reorder_lead_time_days=payload.reorder_lead_time_days,
        preferred_supplier_id=payload.preferred_supplier_id,
        suppliers=suppliers,
    )
    db.add(product)
    db.flush()
    set_opening_stock(db, product, payload.opening_stock)
    db.commit()
    db.refresh(product)
    return _to_out(product, payload.opening_stock)


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, payload: ProductUpdate, db: DbSession, _: OwnerUser
) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    data = payload.model_dump(exclude_unset=True)
    supplier_ids = data.pop("supplier_ids", None)
    if supplier_ids is not None:
        product.suppliers = _resolve_suppliers(db, supplier_ids)
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
    for field, value in data.items():
        setattr(product, field, value)

    if product.preferred_supplier_id is not None:
        allowed = {s.id for s in product.suppliers}
        if product.preferred_supplier_id not in allowed:
            supplier = db.get(Supplier, product.preferred_supplier_id)
            if supplier is None:
                raise HTTPException(status_code=400, detail="Preferred supplier not found.")
            product.suppliers.append(supplier)

    db.commit()
    db.refresh(product)
    return _to_out(product, current_stock_map(db, [product_id]).get(product_id, 0))


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DbSession, _: OwnerUser) -> None:
    """Deactivates rather than deletes once the product has any history.

    Hard-deleting would take sales and purchase records with it, breaking the
    audit trail the whole system rests on.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    has_history = db.execute(
        select(func.count(SaleItem.id)).where(SaleItem.product_id == product_id)
    ).scalar_one() or db.execute(
        select(func.count(PurchaseItem.id)).where(PurchaseItem.product_id == product_id)
    ).scalar_one()

    if has_history:
        product.is_active = False
    else:
        db.delete(product)
    db.commit()
