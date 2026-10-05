"""Reduce stock on fast-moving staples so the recommendation engine
has several at-risk candidates. Run once, from backend/:

    python seed_shortages.py
"""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import InventoryMovement, MovementSource, Product
from app.services.inventory import current_stock_map

SHORTAGES = {
    "MF2KG":  40, "OIL1L": 50, "SUG1KG": 100,
    "BRD400": 30, "MLK500": 60, "EGG30": 6,
    "RIC1KG": 40, "TEA250": 20, "SOD500": 30,
}

def main() -> int:
    db = SessionLocal()
    try:
        all_products = db.query(Product).all()
        ids = [p.id for p in all_products]
        stock_before = current_stock_map(db, ids)
        print(f"Loaded {len(all_products)} products. Stock map size: {len(stock_before)}")

        by_sku = {p.sku: p for p in all_products}
        changed = 0
        for sku, amount in SHORTAGES.items():
            p = by_sku.get(sku)
            if p is None:
                print(f"  skip: {sku} not found"); continue
            on_hand = stock_before.get(p.id, 0)
            if on_hand <= amount:
                print(f"  skip: {sku} already at or below {amount} (currently {on_hand})")
                continue
            new_stock = on_hand - amount
            db.add(InventoryMovement(
                product_id=p.id, change_qty=-amount,
                source_type=MovementSource.adjustment, source_id=None,
                resulting_stock=new_stock,
                note="Evaluation: reduce stock to create shortage scenario",
                timestamp=datetime.now(timezone.utc),
            ))
            print(f"  {sku}: {on_hand} -> {new_stock} (-{amount})")
            changed += 1
        db.commit()
        print(f"\nDone. {changed} products adjusted.")
        return 0
    except Exception as e:
        db.rollback()
        print(f"Error: {e!r}")
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())