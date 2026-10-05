"""Show per-product stock risk at 30-day horizon for debugging."""
from app.database import SessionLocal
from app.services.recommendation import assess_stock_risk

db = SessionLocal()
try:
    rows = assess_stock_risk(db, horizon_days=30)
    print(f"{'SKU':<8} {'stock':>6} {'demand':>8} {'shortage':>9} {'at_risk':>8}  reason")
    print("-" * 100)
    for r in rows:
        demand = r["forecast_demand"]
        demand_str = f"{demand:.2f}" if demand is not None else "None"
        print(
            f"{r['sku']:<8} {r['current_stock']:>6} {demand_str:>8} "
            f"{r['estimated_shortage']:>9} {str(r['at_risk']):>8}  {r['reason'][:50]}"
        )
finally:
    db.close()