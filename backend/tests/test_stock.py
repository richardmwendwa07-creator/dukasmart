"""Stock derivation: sales reduce it, purchases increase it, and nothing partially commits."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import InventoryMovement, MovementSource, Sale, SaleItem
from app.services.inventory import (
    BusinessRuleError,
    current_stock,
    record_adjustment,
    record_purchase,
    record_sale,
)


def test_sale_reduces_stock(db, owner, make_product):
    product = make_product("Sugar 1kg", "SUG1", selling_price=165.0, opening_stock=50)
    assert current_stock(db, product.id) == 50

    sale = record_sale(
        db, user=owner, sale_date=date.today(), items=[{"product_id": product.id, "quantity": 12}]
    )
    db.commit()

    assert current_stock(db, product.id) == 38
    assert sale.total_amount == pytest.approx(12 * 165.0)

    # A SaleItem and a matching movement were both written.
    items = db.execute(select(SaleItem).where(SaleItem.sale_id == sale.id)).scalars().all()
    assert len(items) == 1
    assert items[0].quantity == 12
    assert items[0].unit_price_at_sale == pytest.approx(165.0)

    movement = db.execute(
        select(InventoryMovement).where(
            InventoryMovement.source_type == MovementSource.sale,
            InventoryMovement.source_id == sale.id,
        )
    ).scalar_one()
    assert movement.change_qty == -12
    assert movement.resulting_stock == 38


def test_purchase_increases_stock(db, owner, supplier, make_product):
    product = make_product("Rice 1kg", "RIC1", opening_stock=10)

    purchase = record_purchase(
        db,
        user=owner,
        supplier_id=supplier.id,
        date_received=date.today(),
        items=[{"product_id": product.id, "quantity_received": 40, "unit_cost": 145.0}],
    )
    db.commit()

    assert current_stock(db, product.id) == 50
    assert purchase.total_cost == pytest.approx(40 * 145.0)

    movement = db.execute(
        select(InventoryMovement).where(
            InventoryMovement.source_type == MovementSource.purchase,
            InventoryMovement.source_id == purchase.id,
        )
    ).scalar_one()
    assert movement.change_qty == 40
    assert movement.resulting_stock == 50


def test_stock_is_derived_from_movements_not_a_counter(db, owner, supplier, make_product):
    """opening + purchases - sales, exactly as spec 4.5 requires."""
    product = make_product("Maize Flour 2kg", "MF2", opening_stock=20)

    record_purchase(
        db,
        user=owner,
        supplier_id=supplier.id,
        date_received=date.today(),
        items=[{"product_id": product.id, "quantity_received": 100, "unit_cost": 150.0}],
    )
    record_sale(
        db, user=owner, sale_date=date.today(), items=[{"product_id": product.id, "quantity": 35}]
    )
    record_sale(
        db, user=owner, sale_date=date.today(), items=[{"product_id": product.id, "quantity": 15}]
    )
    db.commit()

    summed = db.execute(
        select(func.sum(InventoryMovement.change_qty)).where(
            InventoryMovement.product_id == product.id
        )
    ).scalar_one()

    assert summed == 20 + 100 - 35 - 15 == 70
    assert current_stock(db, product.id) == 70

    # The running snapshot on the newest movement agrees with the derived total.
    newest = db.execute(
        select(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
        .order_by(InventoryMovement.id.desc())
        .limit(1)
    ).scalar_one()
    assert newest.resulting_stock == 70


def test_multi_line_sale_updates_every_product(db, owner, make_product):
    a = make_product("Bread 400g", "BRD4", selling_price=70.0, opening_stock=30)
    b = make_product("Milk 500ml", "MLK5", selling_price=60.0, opening_stock=25)

    sale = record_sale(
        db,
        user=owner,
        sale_date=date.today(),
        items=[
            {"product_id": a.id, "quantity": 4},
            {"product_id": b.id, "quantity": 6},
        ],
    )
    db.commit()

    assert current_stock(db, a.id) == 26
    assert current_stock(db, b.id) == 19
    assert sale.total_amount == pytest.approx(4 * 70.0 + 6 * 60.0)


def test_oversell_is_rejected_and_nothing_is_written(db, owner, make_product):
    """The key atomicity guarantee: a rejected line leaves no trace at all."""
    ok = make_product("Salt 1kg", "SLT1", opening_stock=100)
    short = make_product("Tea 250g", "TEA2", opening_stock=3)

    sales_before = db.execute(select(func.count(Sale.id))).scalar_one()
    movements_before = db.execute(select(func.count(InventoryMovement.id))).scalar_one()

    with pytest.raises(BusinessRuleError, match="Not enough"):
        record_sale(
            db,
            user=owner,
            sale_date=date.today(),
            items=[
                {"product_id": ok.id, "quantity": 5},   # this line alone would succeed
                {"product_id": short.id, "quantity": 9},  # this one cannot
            ],
        )
    db.rollback()

    assert db.execute(select(func.count(Sale.id))).scalar_one() == sales_before
    assert db.execute(select(func.count(InventoryMovement.id))).scalar_one() == movements_before
    # Crucially, the *first* product's stock was not touched.
    assert current_stock(db, ok.id) == 100
    assert current_stock(db, short.id) == 3


def test_negative_and_zero_quantities_are_rejected(db, owner, make_product):
    product = make_product("Soda 500ml", "SOD5", opening_stock=50)

    with pytest.raises(BusinessRuleError):
        record_sale(
            db, user=owner, sale_date=date.today(), items=[{"product_id": product.id, "quantity": 0}]
        )
    db.rollback()

    with pytest.raises(BusinessRuleError):
        record_sale(
            db, user=owner, sale_date=date.today(), items=[{"product_id": product.id, "quantity": -5}]
        )
    db.rollback()

    assert current_stock(db, product.id) == 50


def test_adjustment_records_an_audited_movement(db, make_product):
    product = make_product("Eggs tray", "EGG3", opening_stock=10)

    record_adjustment(db, product_id=product.id, change_qty=-3, note="Two cracked, one expired")
    db.commit()

    assert current_stock(db, product.id) == 7
    movement = db.execute(
        select(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
        .order_by(InventoryMovement.id.desc())
        .limit(1)
    ).scalar_one()
    assert movement.source_type == MovementSource.adjustment
    assert movement.note == "Two cracked, one expired"


def test_adjustment_cannot_push_stock_below_zero(db, make_product):
    product = make_product("Cooking Oil 1L", "OIL1", opening_stock=4)
    with pytest.raises(BusinessRuleError, match="below zero"):
        record_adjustment(db, product_id=product.id, change_qty=-9, note="Stock take")
    db.rollback()
    assert current_stock(db, product.id) == 4


def test_purchase_links_supplier_to_product(db, owner, supplier, make_product):
    product = make_product("Washing Powder", "WSH5", opening_stock=0)
    record_purchase(
        db,
        user=owner,
        supplier_id=supplier.id,
        date_received=date.today(),
        items=[{"product_id": product.id, "quantity_received": 12, "unit_cost": 158.0}],
    )
    db.commit()
    db.refresh(product)
    assert supplier.id in {s.id for s in product.suppliers}
    assert product.preferred_supplier_id == supplier.id
