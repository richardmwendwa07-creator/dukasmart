"""Stock derivation and the atomic stock-changing operations.

The golden rule of this module: **stock is never stored, only derived.**
``current_stock(product)`` is ``SUM(inventory_movements.change_qty)``. Each
movement also records ``resulting_stock`` as a point-in-time snapshot so the
audit trail reads naturally, but that column is a convenience, never the truth.

Every public function that changes stock does so inside a single database
transaction: either the Sale + SaleItems + InventoryMovements all land, or none
of them do.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    InventoryMovement,
    MovementSource,
    Product,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    User,
)


class BusinessRuleError(Exception):
    """Raised for input that is well-formed but not allowed by the business rules.

    Routers translate this into an HTTP 400 with the message shown to the user,
    so messages must be written in plain language.
    """


# --------------------------------------------------------------------------
# Derivation
# --------------------------------------------------------------------------
def current_stock(db: Session, product_id: int) -> int:
    total = db.execute(
        select(func.coalesce(func.sum(InventoryMovement.change_qty), 0)).where(
            InventoryMovement.product_id == product_id
        )
    ).scalar_one()
    return int(total or 0)


def current_stock_map(db: Session, product_ids: list[int] | None = None) -> dict[int, int]:
    """Stock for many products in one query (avoids N+1 on list screens)."""
    stmt = select(
        InventoryMovement.product_id,
        func.coalesce(func.sum(InventoryMovement.change_qty), 0),
    ).group_by(InventoryMovement.product_id)
    if product_ids is not None:
        if not product_ids:
            return {}
        stmt = stmt.where(InventoryMovement.product_id.in_(product_ids))
    rows = db.execute(stmt).all()
    result = {int(pid): int(qty or 0) for pid, qty in rows}
    if product_ids is not None:
        for pid in product_ids:
            result.setdefault(pid, 0)
    return result


def _record_movement(
    db: Session,
    *,
    product_id: int,
    change_qty: int,
    source_type: MovementSource,
    source_id: int | None,
    running_stock: int,
    note: str | None = None,
) -> InventoryMovement:
    """Append one movement. ``running_stock`` is the stock *after* this change."""
    movement = InventoryMovement(
        product_id=product_id,
        change_qty=change_qty,
        source_type=source_type,
        source_id=source_id,
        resulting_stock=running_stock,
        note=note,
    )
    db.add(movement)
    return movement


def _load_products(db: Session, product_ids: list[int]) -> dict[int, Product]:
    products = db.execute(select(Product).where(Product.id.in_(product_ids))).scalars().all()
    found = {p.id: p for p in products}
    missing = [pid for pid in product_ids if pid not in found]
    if missing:
        raise BusinessRuleError(
            f"Product(s) not found: {', '.join(str(m) for m in missing)}. "
            "Refresh the product list and try again."
        )
    return found


# --------------------------------------------------------------------------
# Opening stock (product creation)
# --------------------------------------------------------------------------
def set_opening_stock(db: Session, product: Product, quantity: int, note: str = "Opening stock") -> None:
    """Seed a brand-new product's shelf count as an adjustment movement.

    Kept as a movement so stock stays fully derivable (spec 4.5:
    opening_stock + purchases - sales).
    """
    if quantity <= 0:
        return
    _record_movement(
        db,
        product_id=product.id,
        change_qty=quantity,
        source_type=MovementSource.adjustment,
        source_id=None,
        running_stock=quantity,
        note=note,
    )


# --------------------------------------------------------------------------
# Sales
# --------------------------------------------------------------------------
def record_sale(
    db: Session,
    *,
    user: User,
    sale_date: date,
    items: list[dict],
    note: str | None = None,
    allow_negative_stock: bool = False,
) -> Sale:
    """Record a sale: Sale + SaleItems + InventoryMovements, all or nothing.

    ``items`` entries: ``{"product_id": int, "quantity": int, "unit_price_at_sale": float|None}``
    """
    if not items:
        raise BusinessRuleError("A sale needs at least one product.")

    product_ids = [int(i["product_id"]) for i in items]
    products = _load_products(db, product_ids)
    stock = current_stock_map(db, product_ids)

    # Validate everything *before* writing anything, so a rejected line never
    # leaves a half-written sale behind.
    for item in items:
        qty = int(item["quantity"])
        if qty <= 0:
            raise BusinessRuleError(
                f"Quantity for {products[item['product_id']].name} must be more than zero."
            )
        price = item.get("unit_price_at_sale")
        if price is not None and float(price) < 0:
            raise BusinessRuleError(
                f"Price for {products[item['product_id']].name} cannot be negative."
            )
        if not allow_negative_stock:
            available = stock.get(int(item["product_id"]), 0)
            if qty > available:
                product = products[int(item["product_id"])]
                raise BusinessRuleError(
                    f"Not enough {product.name} in stock: you have {available} but tried to "
                    f"sell {qty}. Record the delivery first, or correct the count."
                )

    # `db.begin_nested()` gives us a SAVEPOINT that rolls back cleanly on error
    # even when the caller already opened a transaction (e.g. the seed script).
    with db.begin_nested():
        sale = Sale(user_id=user.id, date=sale_date, total_amount=0.0, note=note)
        db.add(sale)
        db.flush()  # assign sale.id

        total = 0.0
        for item in items:
            pid = int(item["product_id"])
            qty = int(item["quantity"])
            product = products[pid]
            unit_price = item.get("unit_price_at_sale")
            unit_price = float(product.selling_price) if unit_price is None else float(unit_price)

            db.add(
                SaleItem(
                    sale_id=sale.id,
                    product_id=pid,
                    quantity=qty,
                    unit_price_at_sale=unit_price,
                )
            )
            total += unit_price * qty

            stock[pid] = stock.get(pid, 0) - qty
            _record_movement(
                db,
                product_id=pid,
                change_qty=-qty,
                source_type=MovementSource.sale,
                source_id=sale.id,
                running_stock=stock[pid],
            )

        sale.total_amount = round(total, 2)
        db.flush()

    return sale


# --------------------------------------------------------------------------
# Purchases
# --------------------------------------------------------------------------
def record_purchase(
    db: Session,
    *,
    user: User,
    supplier_id: int,
    date_received: date,
    items: list[dict],
    note: str | None = None,
) -> Purchase:
    """Record stock received: Purchase + PurchaseItems + InventoryMovements, atomically."""
    if not items:
        raise BusinessRuleError("A delivery needs at least one product.")

    product_ids = [int(i["product_id"]) for i in items]
    products = _load_products(db, product_ids)
    stock = current_stock_map(db, product_ids)

    for item in items:
        if int(item["quantity_received"]) <= 0:
            raise BusinessRuleError(
                f"Quantity for {products[int(item['product_id'])].name} must be more than zero."
            )
        if float(item["unit_cost"]) < 0:
            raise BusinessRuleError(
                f"Cost for {products[int(item['product_id'])].name} cannot be negative."
            )

    with db.begin_nested():
        purchase = Purchase(
            user_id=user.id,
            supplier_id=supplier_id,
            date_received=date_received,
            total_cost=0.0,
            note=note,
        )
        db.add(purchase)
        db.flush()

        total = 0.0
        for item in items:
            pid = int(item["product_id"])
            qty = int(item["quantity_received"])
            unit_cost = float(item["unit_cost"])

            db.add(
                PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=pid,
                    quantity_received=qty,
                    unit_cost=unit_cost,
                )
            )
            total += unit_cost * qty

            stock[pid] = stock.get(pid, 0) + qty
            _record_movement(
                db,
                product_id=pid,
                change_qty=qty,
                source_type=MovementSource.purchase,
                source_id=purchase.id,
                running_stock=stock[pid],
            )

            # Link the product to this supplier if it is a new pairing, so the
            # "who do I buy this from" answer stays current.
            product = products[pid]
            if supplier_id not in {s.id for s in product.suppliers}:
                from ..models import Supplier

                supplier = db.get(Supplier, supplier_id)
                if supplier is not None:
                    product.suppliers.append(supplier)
            if product.preferred_supplier_id is None:
                product.preferred_supplier_id = supplier_id

        purchase.total_cost = round(total, 2)
        db.flush()

    return purchase


# --------------------------------------------------------------------------
# Manual adjustments (stock-take corrections, breakages, expiry)
# --------------------------------------------------------------------------
def record_adjustment(
    db: Session, *, product_id: int, change_qty: int, note: str, allow_negative_stock: bool = False
) -> InventoryMovement:
    if change_qty == 0:
        raise BusinessRuleError("Adjustment cannot be zero.")
    product = db.get(Product, product_id)
    if product is None:
        raise BusinessRuleError("Product not found.")

    available = current_stock(db, product_id)
    new_stock = available + change_qty
    if new_stock < 0 and not allow_negative_stock:
        raise BusinessRuleError(
            f"That would take {product.name} below zero (you have {available}). "
            "Check the number and try again."
        )

    with db.begin_nested():
        movement = _record_movement(
            db,
            product_id=product_id,
            change_qty=change_qty,
            source_type=MovementSource.adjustment,
            source_id=None,
            running_stock=new_stock,
            note=note,
        )
        db.flush()
    return movement


# --------------------------------------------------------------------------
# Costing helper shared by the recommendation engine
# --------------------------------------------------------------------------
def latest_unit_costs(db: Session, product_ids: list[int] | None = None) -> dict[int, float]:
    """Most recent actual purchase cost per product.

    Assumption (documented in the README): the best estimate of what restocking
    will cost is what the shop last actually paid. Products never purchased fall
    back to ``Product.default_unit_cost`` — handled by the caller.
    """
    if product_ids is not None and not product_ids:
        return {}

    # Rank purchase items by (date_received, purchase id) and keep the newest.
    stmt = (
        select(PurchaseItem.product_id, PurchaseItem.unit_cost)
        .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
        .order_by(PurchaseItem.product_id, Purchase.date_received.asc(), Purchase.id.asc())
    )
    if product_ids is not None:
        stmt = stmt.where(PurchaseItem.product_id.in_(product_ids))

    latest: dict[int, float] = {}
    for pid, cost in db.execute(stmt).all():
        latest[int(pid)] = float(cost)  # later rows overwrite earlier ones
    return latest
