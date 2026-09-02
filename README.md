# DukaSmart

Budget-aware demand forecasting and inventory decision support for small Kenyan retail
shops. Turns everyday sales and delivery records into a live stock position, an honest
demand forecast, and a prioritised restock plan that respects the money actually available.

**Decision support, not automation** — DukaSmart explains every recommendation and lets the
operator accept, change, or reject it. It never places an order and never moves money.

📖 **[Full documentation → `docs/README.md`](docs/README.md)** — setup, the forecasting
approach, the priority-score weights, and every assumption made.

---

## Run it

```bash
# 1. Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r backend/requirements.txt
python backend/seed.py --reset      # ~3 months of realistic demo data
python -m uvicorn app.main:app --reload --app-dir backend --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and sign in as **`owner@dukasmart.co.ke` / `duka1234`**.

API docs: <http://127.0.0.1:8000/docs>

```bash
# Tests
cd backend && python -m pytest -q      # 48 passing
```

---

## What it does

| | |
|---|---|
| **Stock** | Derived from an append-only movement trail (`SUM(change_qty)`), never a mutable counter. Every sale, delivery, and correction is auditable per product. |
| **Forecasting** | Three models compete per product on a time-ordered hold-out — weighted moving average, exponential smoothing, and gradient boosting over lag/rolling/calendar features. Lowest MAE wins. |
| **Honesty gate** | Products with fewer than 10 selling days or 28 days of history are flagged `insufficient_data` rather than guessed at. |
| **Restock plan** | Ranks at-risk products by `0.50 × stockout risk + 0.30 × demand velocity + 0.20 × cost efficiency`, then allocates the budget top-down, showing the shortfall. |
| **Human in the loop** | Accept / change / reject each line. Accepting never moves stock. |
| **Reports** | Sales, deliveries, forecast accuracy (predicted vs. actual), and plans vs. what was actually bought. |

## Stack

FastAPI · SQLAlchemy 2 · SQLite · pandas / scikit-learn / statsmodels · JWT + bcrypt
React · Vite · TanStack Query · Recharts · Tailwind CSS v4

## Layout

```
backend/    API, models, forecasting engine, business logic, tests, seed script
frontend/   React SPA (mobile-first — many owners use a phone)
docs/       Full README: setup, forecasting approach, weights, assumptions
```
