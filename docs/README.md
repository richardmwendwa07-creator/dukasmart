# DukaSmart

Budget-aware demand forecasting and inventory decision support for small retail shops
("dukas") in Kenya.

DukaSmart turns everyday sales and delivery records into three things a shop owner
actually needs:

1. **An always-current stock position** per product, derived from an audit trail rather
   than a mutable counter.
2. **A demand forecast** per product — generated *only* where there is enough sales
   history to be honest about it.
3. **A prioritised, budget-constrained restock plan** — which products to buy first when
   there isn't enough money to buy everything.

> **This is decision support, not automation.** DukaSmart explains every recommendation
> and lets the operator accept, change, or reject each line. It never places an order and
> never moves money.

---

## 1. Quick start

### Prerequisites

- **Python 3.10+** (developed and tested on 3.14)
- **Node.js 18+** (developed and tested on 24)

### Backend

```bash
# from the project root
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt

# Create the database and fill it with ~3 months of realistic demo data
python backend/seed.py --reset

# Run the API
python -m uvicorn app.main:app --reload --app-dir backend --port 8000
```

The API is now on <http://127.0.0.1:8000>, with interactive docs at
<http://127.0.0.1:8000/docs>.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to the backend, so the
browser only ever talks to one origin.

### Demo sign-in

The seed script creates two accounts (both password `duka1234`):

| Email | Role | Can do |
|---|---|---|
| `owner@dukasmart.co.ke` | Owner | Everything, including budgets and restock plans |
| `staff@dukasmart.co.ke` | Assistant | Record sales and deliveries; view stock |

### Single-process deployment (optional)

```bash
cd frontend && npm run build
```

If `frontend/dist` exists, the FastAPI app serves it directly — one process on port 8000,
no separate frontend server.

### Tests

```bash
cd backend
python -m pytest -q
```

48 tests covering stock arithmetic, transaction atomicity, the data-sufficiency gate,
forecast reproducibility, budget-constrained prioritisation, and the HTTP/auth surface.

---

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python + FastAPI** | The forecasting work is Python-native, so keeping one language avoids a cross-process hop |
| Database | **SQLite via SQLAlchemy 2.0** | Zero-setup for a prototype; the ORM layer means Postgres is a connection-string change |
| Forecasting | **pandas, scikit-learn, statsmodels** | In-process, same runtime as the API |
| Frontend | **React + Vite** | SPA with a real build pipeline |
| Data fetching | **TanStack Query** | Cache invalidation after every mutation, so stock figures are never stale |
| Charts | **Recharts** | Responsive SVG charts that work on a phone |
| Styling | **Tailwind CSS v4** | Mobile-first, large touch targets |
| Icons / toasts | **lucide-react, sonner** | Immediate feedback on every action |
| Auth | **JWT + bcrypt** | Stateless tokens; passwords are hashed, never stored or logged |

---

## 3. Project layout

```
backend/
  app/
    config.py                 every tunable in one place (env-overridable)
    database.py               engine, session, FK/WAL pragmas
    models.py                 SQLAlchemy models
    schemas.py                Pydantic request/response validation
    security.py               bcrypt hashing + JWT issuing
    deps.py                   current-user and owner-only dependencies
    main.py                   app wiring, dashboard summary, SPA hosting
    routers/                  auth, catalog, transactions, inventory,
                              forecasts, planning, reports
    services/
      inventory.py            stock derivation + atomic stock operations
      forecasting.py          the forecasting engine
      recommendation.py       risk detection + budget allocation
  tests/                      48 tests
  seed.py                     realistic demo data generator
frontend/
  src/
    lib/api.js                typed-ish API client + KES formatting
    lib/auth.jsx              session context
    components/               Layout (responsive nav) + UI primitives
    pages/                    11 screens
docs/README.md                this file
```

---

## 4. How stock is derived

**The golden rule: stock is never stored, only derived.**

`Product` deliberately has **no** `stock` column. Current stock is:

```sql
SELECT SUM(change_qty) FROM inventory_movements WHERE product_id = ?
```

Every stock change appends an `InventoryMovement` row recording the delta, its source
(`sale` / `purchase` / `adjustment`), the source record's id, and the resulting running
total. This satisfies the spec's `opening_stock + purchases − sales` requirement while
staying fully auditable: the Stock screen shows the complete movement history per product,
and the running total on each row can be checked against the derived sum.

`resulting_stock` is stored on each movement as a point-in-time snapshot for readability —
it is a convenience, never the source of truth.

### Atomicity

Every stock-changing operation is wrapped in a single transaction (`db.begin_nested()`,
a SAVEPOINT, so it composes correctly when the caller already has a transaction open):

- **Sale** → `Sale` + N × `SaleItem` + N × `InventoryMovement`, all or nothing
- **Delivery** → `Purchase` + N × `PurchaseItem` + N × `InventoryMovement`, all or nothing
- **Adjustment** → one `InventoryMovement`

All validation happens *before* any write, so a rejected line never leaves a half-written
sale behind. This is covered directly by
`test_oversell_is_rejected_and_nothing_is_written`: a two-line sale where the first line
would succeed and the second cannot leaves *both* products' counts untouched.

---

## 5. The forecasting approach

### Step 1 — Build a dense daily series

For each product, sales are aggregated into units-per-calendar-day from the first recorded
sale up to today, **zero-filled**. Days with no sale are real information: a sparse series
makes a slow seller look like a fast one.

### Step 2 — The data-sufficiency gate

A product is forecast **only** if it has:

- at least **10** days with a non-zero sale (`DUKASMART_MIN_NONZERO_OBSERVATIONS`), **and**
- at least **28** days of history span (`DUKASMART_MIN_HISTORY_DAYS`)

Otherwise the Forecast row is written with `data_sufficiency_flag = insufficient_data`, a
`NULL` predicted quantity, and a plain-language `insufficiency_reason`. The UI says
"not enough sales history yet" rather than showing a number.

*This is deliberate.* Guessing from four data points would be worse than silence — the
operator would spend real money on it.

### Step 3 — Time-ordered hold-out

The most recent **14** days become the test window; everything before is training. Capped
at 30% of history, and always leaving at least 21 training days.

**Never a random split** — that leaks the future into the past and flatters the model.

### Step 4 — Model bake-off

Three candidates compete on the same hold-out window:

| Model | What it is | Shown to the operator as |
|---|---|---|
| `weighted_moving_average` | Baseline. Linearly weighted average of the last 14 days, newest weighted highest | "Recent average" |
| `simple_exponential_smoothing` | Baseline. statsmodels SES, α estimated by MLE | "Smoothed trend" |
| `gradient_boosting` | scikit-learn `HistGradientBoostingRegressor` over lag (1,2,3,7,14), rolling mean (7,14,28), rolling std, and calendar features (day-of-week, weekend, day-of-month, month-start/end, week-of-year, trend). Multi-step forecasting is recursive | "Pattern learner" |

Rolling features are shifted by one day so a row never sees its own target — no leakage.

**Scoring:** MAE on the hold-out window. MAPE is also computed but only over days where at
least 1 unit sold and at least 3 such days exist — a percentage error against a near-zero
actual is meaningless.

**Winner:** lowest MAE. Ties within 1% break toward the *simpler* model, so complexity has
to earn its place.

On the seeded demo data, all three models win on different products — no single method
dominates, which is exactly why the bake-off is per-product.

### Step 5 — Refit and forecast

The winner is refit on the **full** history (not just the training slice) and used to
predict each day of the horizon. `predicted_quantity` is the sum. Forecasts are floored at
zero — demand cannot be negative.

Horizon is configurable: **7, 14, or 30 days**.

### Reproducibility

Every Forecast row stores what is needed to explain or repeat the run:

- `model_used` and full `model_params` (including the random seed, and the day-by-day
  predictions used to draw the chart)
- `data_window_start` / `data_window_end` — exactly which dates went in
- `observations_used`, `nonzero_observations`, `bucket`, `holdout_days`
- `error_metrics` (MAE/MAPE) and `candidate_scores` — **every** model that competed and
  what it scored, including any that failed to fit and why

The "How this was worked out" panel on the Sales Outlook screen surfaces all of it.
`random_state=42` on the tree model means the same data in gives the same forecast out —
verified by `test_same_input_gives_the_same_forecast`.

---

## 6. Stockout-risk detection

For each product with a valid forecast:

```
daily_rate       = forecast_demand / horizon_days
lead_time_demand = daily_rate × reorder_lead_time_days      (0 if unknown)
safety_stock     = safety_margin_pct × (forecast_demand + lead_time_demand)
projected_need   = forecast_demand + lead_time_demand + safety_stock
shortage         = ceil(max(0, projected_need − current_stock))
```

A product is **at risk** when `shortage > 0`. Default safety margin is **20%**,
adjustable in the UI from 0–60%.

Lead time is included because stock has to last not just through the horizon but through
the wait for the next delivery.

---

## 7. The priority score — weights and rationale

When the budget covers everything, ranking is irrelevant: every at-risk product gets its
full required quantity.

When it doesn't, each at-risk product is scored on three normalised 0–1 factors:

```
priority = 0.50 × stockout_risk
         + 0.30 × demand_velocity
         + 0.20 × cost_efficiency
```

| Factor | Weight | Definition | Why this weight |
|---|---|---|---|
| **Stockout risk** | **50%** | `shortage / projected_need` — what fraction of what you need is missing. 1.0 = empty shelf | Running out is the failure the shop feels most directly: lost sales today, and customers who go elsewhere tomorrow |
| **Demand velocity** | **30%** | `daily_rate`, min-max normalised across the at-risk set | Fast movers convert stock back into cash soonest, so the same shilling works harder |
| **Cost efficiency** | **20%** | `(selling_price − unit_cost) / unit_cost` — gross margin per shilling spent, min-max normalised. Falls back to `1 / unit_cost` (cheap-first) if no product has a recorded margin | Rewards turning a limited budget into the most profit, but deliberately weighted lowest: a high-margin item nobody is about to run out of is not urgent |

Weights are set in `backend/app/config.py`, overridable via `DUKASMART_WEIGHT_*`, and
validated at import time to sum to 1.0. **Every run stores the weights it used**, so an old
recommendation stays explainable even after the weights change.

### Budget allocation

- `total_required_cost <= budget` → everyone gets their full required quantity.
- Otherwise → walk top-down by rank, giving each product as much as the remaining budget
  allows. A **partial fill is better than nothing**. If a product can't be afforded at all,
  keep walking — a cheaper item further down may still fit.

This is a **greedy allocation**, chosen deliberately over an optimal knapsack solve: it can
be justified line-by-line to a shop owner ("this one first, because…"), which matters more
here than squeezing out a few extra units.

Every line shows current stock, forecast demand, lead-time cover, safety cushion, estimated
shortage, unit cost, recommended quantity, recommended cost, the three score components as
bars, and the priority rank — plus a written explanation in plain language.

### The operator decides

Each line can be **accepted**, **changed** (enter a different quantity), or **rejected**,
and the decision is persisted with a timestamp. Accepting a recommendation does **not**
move stock — verified by `test_recommendation_never_places_an_order`. Stock only changes
when a real delivery is recorded.

---

## 8. Roles

| | Owner | Assistant |
|---|---|---|
| Record sales / deliveries | ✅ | ✅ |
| View stock, movements, sales outlook | ✅ | ✅ |
| Correct shelf counts | ✅ | ✅ |
| Add/edit products and suppliers | ✅ | ❌ |
| Set budgets | ✅ | ❌ |
| Run and decide restock plans | ✅ | ❌ |

The first account ever registered automatically becomes the owner.

---

## 9. Security notes

- Passwords hashed with **bcrypt**; minimum 8 characters, 72-byte maximum enforced
  explicitly (bcrypt silently truncates past 72, which would make two different passwords
  equivalent).
- Passwords are never returned by any endpoint, and the validation error handler
  deliberately does **not** echo the submitted value back — so a mistyped password can't
  end up in an error body or a log line.
- Login returns an identical message for "unknown email" and "wrong password", so the
  endpoint can't be used to enumerate accounts.
- JWTs are signed HS256. **The default `secret_key` is a development placeholder — set
  `DUKASMART_SECRET_KEY` before deploying anywhere real.**
- SQLite foreign-key enforcement is switched on explicitly (it's off by default).

---

## 10. Configuration

All settings live in `backend/app/config.py`, overridable by environment variable with a
`DUKASMART_` prefix or a `backend/.env` file.

| Variable | Default | Meaning |
|---|---|---|
| `DUKASMART_DATABASE_URL` | `sqlite:///backend/dukasmart.db` | Point at Postgres to switch |
| `DUKASMART_SECRET_KEY` | dev placeholder | **Change in production** |
| `DUKASMART_MIN_NONZERO_OBSERVATIONS` | `10` | Days-with-a-sale needed before forecasting |
| `DUKASMART_MIN_HISTORY_DAYS` | `28` | History span needed before forecasting |
| `DUKASMART_HOLDOUT_DAYS` | `14` | Size of the model-comparison test window |
| `DUKASMART_DEFAULT_HORIZON_DAYS` | `14` | Default look-ahead |
| `DUKASMART_ALLOWED_HORIZONS` | `7,14,30` | Horizons offered in the UI |
| `DUKASMART_DEFAULT_SAFETY_MARGIN_PCT` | `0.20` | Default safety cushion |
| `DUKASMART_WEIGHT_STOCKOUT_RISK` | `0.50` | Priority weight |
| `DUKASMART_WEIGHT_DEMAND_VELOCITY` | `0.30` | Priority weight |
| `DUKASMART_WEIGHT_COST_EFFICIENCY` | `0.20` | Priority weight |

---

## 11. The seed data

`python backend/seed.py --reset` generates a realistic Nairobi duka:

- 4 suppliers, 16 products, ~90 days of daily sales
- Weekly rhythm (weekends busier, Mondays slow), month-end payday bump, mild upward trend
  on two fast movers, Poisson noise so nothing is perfectly predictable
- Weekly restocks that stop 3 days before "today", with per-product cover targets varying
  from 5 to 26 days — so the shop ends with a realistic *spread*: some products nearly
  empty, some comfortable
- **Two deliberately sparse products** (Cocoa Drink, Shoe Polish) with only ~5 scattered
  sales, to exercise the insufficient-data path
- Two budgets: a tight **KES 25,000** (forces prioritisation — the full top-up costs about
  KES 137,000) and a generous **KES 120,000**

`random.Random(20260826)` is seeded, so the dataset is reproducible.

---

## 12. Assumptions made

Where the specification left a detail open, the simplest reasonable option was taken:

1. **Quantities are whole units** (packets, bottles, tins) rather than fractional weights.
   Dukas overwhelmingly sell pre-packaged units. Moving to decimal quantities means
   changing the `Integer` columns to `Numeric`.
2. **Money is `NUMERIC(12,2)` surfaced to Python as `float`**, to keep the pandas and JSON
   layers simple. A system handling real cash at scale should use `Decimal` throughout.
3. **Purchase cost.** `Product` carries a `default_unit_cost`, but the recommendation
   engine prefers the **most recent actual `PurchaseItem` cost** when one exists — what you
   last actually paid is the better estimate of what restocking will cost. Products with
   neither are excluded from the plan and reported as a count, since they can't be budgeted
   for.
4. **`Sale.date` is a date, not a timestamp.** Daily buckets are the forecasting unit;
   time-of-day would add nothing.
5. **Sales cannot drive stock negative.** The API rejects overselling with a clear message
   rather than allowing a negative shelf count. Genuine discrepancies are handled through
   an explicit *adjustment*, which is recorded with a mandatory reason.
6. **Product deletion is a soft delete** once a product has any history — hard-deleting
   would take sales records with it and break the audit trail. Products with no history are
   deleted outright.
7. **Suppliers are many-to-many with products**, plus a nullable `preferred_supplier_id`
   for "who do I normally buy this from". Recording a delivery automatically links the
   supplier to the product.
8. **Logout is client-side.** JWTs are stateless; the client discards the token. A
   production system wanting immediate revocation needs a token denylist or short-lived
   tokens plus refresh.
9. **Forecast accuracy is only scored once the horizon has elapsed.** A forecast made today
   covering the next 14 days is reported as "still running", not scored against partial
   data.
10. **Recommendation follow-through** counts deliveries of that product recorded on or
    after the plan date. Linking a delivery to a specific recommendation would need the
    operator to tag it, which is friction a duka owner won't accept.
11. **A `RecommendationRun` table** was added (not in the spec's entity list) to group the
    line items of one run, so budget totals and reporting have somewhere sensible to live.
12. **Concurrency.** SQLite serialises writes, which is correct for the expected scale
    (a handful of users). On Postgres, high-contention stock updates would want
    `SELECT … FOR UPDATE` on the movement rows.

---

## 13. What is deliberately *not* built

Per the specification: no autonomous purchasing, no supplier payments, no price-negotiation
automation, no IoT or shelf hardware, and no general ERP. The analytical scope is
product-level short-term demand forecasting and replenishment decision support only.

---

## 14. Plain language in the UI

The interface avoids system vocabulary throughout, because the person using it is running a
shop, not an inventory system:

| Internally | Shown to the operator |
|---|---|
| Stockout risk classification | Products running low |
| Insufficient data | Not enough sales history yet |
| Forecast horizon | Look ahead / Next 14 days |
| Purchase recommendation | What to buy |
| Inventory movement | What happened to this product |
| `gradient_boosting` | Pattern learner |
| MAE | Typical daily miss |
| Priority score components | How empty the shelf is / How fast it sells / Profit per shilling spent |
