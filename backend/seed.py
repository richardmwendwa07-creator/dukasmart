"""Seed DukaSmart with realistic sample data so the demo works immediately.

Generates ~90 days of synthetic daily sales for a small Nairobi duka, with
patterns the forecasting engine should actually be able to learn:

* a weekly rhythm (weekends busier, Monday slow)
* a month-end / month-start payday bump
* a mild upward trend on a couple of fast movers
* Poisson noise, so no product is perfectly predictable
* two deliberately sparse products to exercise the insufficient-data path
* stock intentionally run down on several products so the recommendation engine
  has something to prioritise against a tight budget

Run:  python backend/seed.py [--reset]
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import Budget, Product, Supplier, User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.inventory import record_purchase, record_sale, set_opening_stock  # noqa: E402

RNG = random.Random(20260826)  # fixed seed -> reproducible demo data

DAYS_OF_HISTORY = 90

SUPPLIERS = [
    ("Mwangi Wholesalers", "0722 114 250", "Dry goods; delivers Tue & Fri."),
    ("Nairobi Fresh Distributors", "0733 908 117", "Milk, bread, eggs. Daily morning run."),
    ("Kericho Trading Co.", "0710 447 802", "Tea, sugar, cooking fat. Best bulk prices."),
    ("Rift Valley Beverages", "0745 220 619", "Sodas and water. Crate deposits apply."),
]

# name, category, sku, sell, cost, lead_days, base_daily_demand, weekend_lift,
# trend_per_day, opening_stock, supplier_index
PRODUCTS = [
    ("Maize Flour 2kg",        "Staples",    "MF2KG",  185.0, 152.0, 2, 11.0, 1.35,  0.020,  40, 0),
    ("Cooking Oil 1L",         "Staples",    "OIL1L",  310.0, 268.0, 3,  5.5, 1.25,  0.012,  22, 2),
    ("Sugar 1kg",              "Staples",    "SUG1KG", 165.0, 138.0, 2,  8.0, 1.20,  0.008,  15, 2),
    ("Rice 1kg",               "Staples",    "RIC1KG", 175.0, 145.0, 3,  4.5, 1.30,  0.005,  30, 0),
    ("Bread 400g",             "Bakery",     "BRD400",  70.0,  58.0, 1, 14.0, 1.15,  0.000,  12, 1),
    ("Fresh Milk 500ml",       "Dairy",      "MLK500",  60.0,  50.0, 1, 18.0, 1.10,  0.010,  20, 1),
    ("Eggs (tray of 30)",      "Dairy",      "EGG30",  480.0, 415.0, 2,  2.2, 1.45,  0.004,   6, 1),
    ("Tea Leaves 250g",        "Beverages",  "TEA250", 145.0, 118.0, 4,  3.0, 1.10,  0.000,  25, 2),
    ("Soda 500ml",             "Beverages",  "SOD500",  70.0,  55.0, 2, 12.0, 1.55,  0.006,  18, 3),
    ("Bottled Water 1L",       "Beverages",  "WTR1L",   50.0,  38.0, 2,  7.0, 1.40,  0.008,  35, 3),
    ("Laundry Soap Bar",       "Household",  "SOAPBR",  65.0,  50.0, 3,  4.0, 1.20,  0.000,  28, 0),
    ("Washing Powder 500g",    "Household",  "WSH500", 190.0, 158.0, 3,  2.5, 1.25,  0.003,  16, 0),
    ("Salt 1kg",               "Staples",    "SLT1KG",  45.0,  33.0, 4,  2.0, 1.05,  0.000,  40, 0),
    ("Matches (pack of 10)",   "Household",  "MTCH10",  30.0,  21.0, 5,  3.5, 1.15,  0.000,  50, 0),
    # --- deliberately sparse: should be flagged `insufficient_data` -------
    ("Cocoa Drink 400g",       "Beverages",  "COC400", 520.0, 445.0, 6,  0.0, 1.00,  0.000,   4, 2),
    ("Shoe Polish 50ml",       "Household",  "SHP50",   95.0,  74.0, 7,  0.0, 1.00,  0.000,   6, 0),
]

# Products whose stock we deliberately leave thin so the budget run has to choose.
SPARSE_SALE_DAYS = 5  # how many scattered days the two sparse products sell on


def _demand_for(day: date, base: float, weekend_lift: float, trend: float, day_index: int) -> int:
    """Expected units for one product on one day, then Poisson-sampled."""
    if base <= 0:
        return 0
    rate = base + trend * day_index
    if day.weekday() >= 5:  # Sat/Sun
        rate *= weekend_lift
    if day.weekday() == 0:  # Monday is slow
        rate *= 0.80
    if day.day >= 27 or day.day <= 3:  # payday window
        rate *= 1.30
    # Poisson via the inverse-transform trick (no numpy dependency in the seed).
    lam = max(rate, 0.01)
    limit, k, p = 2.718281828459045 ** -lam, 0, 1.0
    while True:
        p *= RNG.random()
        if p <= limit:
            return k
        k += 1
        if k > 200:  # safety valve
            return k


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Database already contains data. Re-run with --reset to start clean.")
            return

        today = date.today()
        start = today - timedelta(days=DAYS_OF_HISTORY - 1)

        # -- users --------------------------------------------------------
        owner = User(
            name="Amina Wanjiru",
            email="owner@dukasmart.co.ke",
            password_hash=hash_password("duka1234"),
            role=UserRole.owner,
        )
        staff = User(
            name="Brian Otieno",
            email="staff@dukasmart.co.ke",
            password_hash=hash_password("duka1234"),
            role=UserRole.staff,
        )
        db.add_all([owner, staff])
        db.flush()

        # -- suppliers ----------------------------------------------------
        suppliers = []
        for name, contact, notes in SUPPLIERS:
            supplier = Supplier(name=name, contact=contact, notes=notes)
            db.add(supplier)
            suppliers.append(supplier)
        db.flush()

        # -- products -----------------------------------------------------
        products = []
        specs = {}
        for (
            name, category, sku, sell, cost, lead, base, lift, trend, opening, sup_idx
        ) in PRODUCTS:
            supplier = suppliers[sup_idx]
            product = Product(
                name=name,
                category=category,
                sku=sku,
                selling_price=sell,
                default_unit_cost=cost,
                reorder_lead_time_days=lead,
                preferred_supplier_id=supplier.id,
                suppliers=[supplier],
            )
            db.add(product)
            db.flush()
            set_opening_stock(db, product, opening, note="Opening stock at go-live")
            products.append(product)
            specs[product.id] = {
                "base": base,
                "lift": lift,
                "trend": trend,
                "cost": cost,
                "supplier": supplier,
                # How many days of demand each restock aims to cover. Varying
                # this is what leaves the shop with a realistic *spread* of
                # closing stock - a few empty shelves, several thin, some fine.
                "cover_days": RNG.uniform(5.0, 26.0),
            }
        db.commit()

        print(f"Generating {DAYS_OF_HISTORY} days of sales for {len(products)} products...")

        # -- sparse products: a handful of scattered sales only ------------
        sparse_days: dict[int, set[int]] = {}
        for product in products:
            if specs[product.id]["base"] <= 0:
                sparse_days[product.id] = set(
                    RNG.sample(range(DAYS_OF_HISTORY), SPARSE_SALE_DAYS)
                )

        # -- day-by-day simulation ----------------------------------------
        # Restock weekly per supplier, but stop a few days before "today" so the
        # shop ends the period mid-cycle â€” which is exactly when an owner would
        # be asking "what should I buy with the money I have?".
        restock_cutoff = DAYS_OF_HISTORY - 3
        # Mirror of the shelf count, so the simulation never sells below zero.
        stock_on_hand = {
            product.id: spec[9]  # opening stock column
            for product, spec in zip(products, PRODUCTS, strict=True)
        }

        for day_index in range(DAYS_OF_HISTORY):
            day = start + timedelta(days=day_index)

            # ---- deliveries (before the day's trading) -------------------
            if day_index < restock_cutoff and day_index % 7 == 2:
                for supplier in suppliers:
                    lines = []
                    for product in products:
                        spec = specs[product.id]
                        if spec["supplier"].id != supplier.id:
                            continue
                        # Top up to this product's own target days of cover.
                        target = int((spec["base"] or 0.4) * spec["cover_days"]) + 4
                        deficit = target - stock_on_hand[product.id]
                        if deficit <= 0:
                            continue
                        qty = int(deficit * RNG.uniform(0.8, 1.15)) or 1
                        unit_cost = round(spec["cost"] * RNG.uniform(0.97, 1.04), 2)
                        lines.append(
                            {
                                "product_id": product.id,
                                "quantity_received": qty,
                                "unit_cost": unit_cost,
                            }
                        )
                        stock_on_hand[product.id] += qty
                    if lines:
                        record_purchase(
                            db,
                            user=owner,
                            supplier_id=supplier.id,
                            date_received=day,
                            items=lines,
                            note="Weekly restock",
                        )

            # ---- the day's sales ----------------------------------------
            lines = []
            for product in products:
                spec = specs[product.id]
                if spec["base"] <= 0:
                    if day_index not in sparse_days.get(product.id, set()):
                        continue
                    qty = RNG.randint(1, 2)
                else:
                    qty = _demand_for(day, spec["base"], spec["lift"], spec["trend"], day_index)
                if qty <= 0:
                    continue
                # Never sell below zero â€” a real duka simply runs out.
                qty = min(qty, stock_on_hand[product.id])
                if qty <= 0:
                    continue
                stock_on_hand[product.id] -= qty
                lines.append({"product_id": product.id, "quantity": qty})

            if lines:
                # Split the day into 1-3 tills so the sale count looks realistic.
                RNG.shuffle(lines)
                chunks = max(1, min(3, len(lines) // 4))
                size = max(1, len(lines) // chunks)
                for i in range(0, len(lines), size):
                    batch = lines[i : i + size]
                    if batch:
                        record_sale(
                            db,
                            user=RNG.choice([owner, staff]),
                            sale_date=day,
                            items=batch,
                        )
            if day_index % 15 == 0:
                db.commit()

        db.commit()

        # -- a budget for the owner to plan against ------------------------
        db.add(
            Budget(
                user_id=owner.id,
                period=today.strftime("%B %Y"),
                amount_available=25000.0,  # deliberately tight -> forces prioritisation
            )
        )
        db.add(
            Budget(
                user_id=owner.id,
                period=f"{today.strftime('%B %Y')} (full restock)",
                amount_available=120000.0,
            )
        )
        db.commit()

        # -- summary -------------------------------------------------------
        from app.models import Purchase, Sale
        from app.services.inventory import current_stock_map

        stock = current_stock_map(db, [p.id for p in products])
        print("\nSeed complete.")
        print(f"  Period            : {start.isoformat()} -> {today.isoformat()}")
        print(f"  Sales recorded    : {db.query(Sale).count()}")
        print(f"  Deliveries recorded: {db.query(Purchase).count()}")
        print(f"  Products          : {len(products)}")
        print("\n  Closing stock:")
        for product in products:
            print(f"    {product.name:<24} {stock.get(product.id, 0):>5}")
        print("\n  Sign in with:")
        print("    owner@dukasmart.co.ke / duka1234   (owner - full access)")
        print("    staff@dukasmart.co.ke / duka1234   (staff - records sales & deliveries)")
        print(f"\n  Database: {settings.database_url}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed DukaSmart with demo data.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first.")
    args = parser.parse_args()

    if args.reset:
        print("Resetting database...")
        reset_database()
    else:
        init_db()
    seed()
