import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  ChevronDown,
  Info,
  Loader2,
  Pencil,
  Wallet,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  EmptyState,
  ErrorNote,
  Field,
  Meter,
  Modal,
  PageHeader,
  Section,
  Spinner,
  Stat,
} from '../components/ui'
import { api, dateTime, money, moneyExact, units } from '../lib/api'

const STATUS_BADGE = {
  proposed: 'badge-muted',
  accepted: 'badge-ok',
  modified: 'badge-info',
  rejected: 'badge-danger',
}
const STATUS_LABEL = {
  proposed: 'Not decided',
  accepted: 'Will buy',
  modified: 'Changed',
  rejected: 'Skipping',
}

/** One recommendation line: the numbers, the reasoning, and the decision buttons. */
function RecommendationCard({ item, rank }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [qty, setQty] = useState(String(item.recommended_quantity))

  const decide = useMutation({
    mutationFn: (body) => api.decide(item.id, body),
    onSuccess: (updated) => {
      toast.success(
        updated.status === 'rejected'
          ? `Skipping ${item.product_name}.`
          : `${item.product_name}: buy ${units(updated.operator_quantity)}.`,
      )
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['recommendation-run'] })
    },
    onError: (err) => toast.error(err.message),
  })

  const funded = item.recommended_quantity
  const needed = item.required_quantity
  const partial = funded > 0 && funded < needed
  const unfunded = funded === 0

  return (
    <div
      className={`rounded-xl ring-1 transition-colors ${
        item.status === 'rejected'
          ? 'bg-slate-50 opacity-70 ring-slate-200'
          : item.status === 'accepted' || item.status === 'modified'
            ? 'bg-emerald-50/40 ring-emerald-200'
            : 'bg-white ring-slate-200'
      }`}
    >
      <div className="flex flex-wrap items-start gap-3 p-4">
        <span
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg text-sm font-bold ${
            rank <= 3 ? 'bg-brand-700 text-white' : 'bg-slate-200 text-slate-700'
          }`}
          title={`Priority ${rank}`}
        >
          {rank}
        </span>

        <div className="min-w-[10rem] flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-slate-900">{item.product_name}</p>
            <span className={STATUS_BADGE[item.status]}>{STATUS_LABEL[item.status]}</span>
            {unfunded && item.status === 'proposed' && (
              <span className="badge-warn">No budget left</span>
            )}
            {partial && <span className="badge-warn">Partly covered</span>}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {units(item.current_stock)} on the shelf · likely to sell{' '}
            {units(item.forecast_demand)} · short {units(item.estimated_shortage)}
          </p>
          {item.supplier_name && (
            <p className="mt-0.5 text-xs text-slate-500">From {item.supplier_name}</p>
          )}
        </div>

        <div className="shrink-0 text-right">
          {editing ? (
            <div className="flex items-center gap-2">
              <input
                className="input !w-24 !py-1.5 text-right"
                type="number"
                min="0"
                step="1"
                inputMode="numeric"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                aria-label="Quantity to buy"
              />
              <button
                type="button"
                className="btn-primary !px-3 !py-1.5"
                onClick={() => {
                  const value = Number(qty)
                  if (!Number.isInteger(value) || value < 0) {
                    toast.error('Enter a whole number, zero or more.')
                    return
                  }
                  decide.mutate({ status: 'modified', quantity: value })
                }}
                disabled={decide.isPending}
              >
                Save
              </button>
              <button
                type="button"
                className="btn-ghost !px-2 !py-1.5"
                onClick={() => {
                  setEditing(false)
                  setQty(String(item.recommended_quantity))
                }}
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
          ) : (
            <>
              <p className="text-xl font-bold tracking-tight text-slate-900">
                {units(
                  item.status === 'proposed' ? item.recommended_quantity : item.operator_quantity,
                )}{' '}
                <span className="text-sm font-normal text-slate-500">units</span>
              </p>
              <p className="text-sm text-slate-500">
                {money(item.recommended_cost)} at {money(item.unit_cost)} each
              </p>
              {needed > funded && (
                <p className="text-xs text-amber-700">
                  {units(needed - funded)} more needed ({money(item.unfunded_cost)})
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {/* ---- decision row ---- */}
      {!editing && (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-2.5">
          <button
            type="button"
            className="btn-secondary !px-3 !py-1.5 !text-xs"
            onClick={() => setOpen((v) => !v)}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
              aria-hidden
            />
            Why this?
          </button>

          <div className="ml-auto flex gap-2">
            <button
              type="button"
              className="btn-secondary !px-3 !py-1.5 !text-xs"
              onClick={() => {
                setQty(String(item.recommended_quantity))
                setEditing(true)
              }}
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
              Change
            </button>
            <button
              type="button"
              className="btn-secondary !px-3 !py-1.5 !text-xs text-rose-700 ring-rose-200 hover:bg-rose-50"
              onClick={() => decide.mutate({ status: 'rejected' })}
              disabled={decide.isPending}
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              Skip
            </button>
            <button
              type="button"
              className="btn-primary !px-3 !py-1.5 !text-xs"
              onClick={() => decide.mutate({ status: 'accepted' })}
              disabled={decide.isPending || item.recommended_quantity === 0}
            >
              {decide.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Check className="h-3.5 w-3.5" aria-hidden />
              )}
              Buy this
            </button>
          </div>
        </div>
      )}

      {/* ---- the reasoning, in full ---- */}
      {open && (
        <div className="border-t border-slate-100 bg-slate-50 p-4">
          <p className="text-sm text-slate-700">{item.reason}</p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <dl className="space-y-1.5 text-sm">
              {[
                ['On the shelf now', units(item.current_stock)],
                ['Likely to sell', units(item.forecast_demand)],
                ['Cover while delivering', units(item.lead_time_demand)],
                ['Safety cushion', units(item.safety_stock)],
                ['Short by', units(item.estimated_shortage)],
                ['Cost each', money(item.unit_cost)],
                ['Full top-up would cost', money(item.required_cost)],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="font-medium text-slate-800">{value}</dd>
                </div>
              ))}
            </dl>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Why it ranks #{rank}
              </p>
              <div className="space-y-2.5">
                <Meter
                  label="How empty the shelf is (50%)"
                  value={item.stockout_risk_score}
                  tone="danger"
                />
                <Meter
                  label="How fast it sells (30%)"
                  value={item.demand_velocity_score}
                  tone="brand"
                />
                <Meter
                  label="Profit per shilling spent (20%)"
                  value={item.cost_efficiency_score}
                  tone="ok"
                />
              </div>
              <p className="mt-3 rounded-lg bg-white p-2 text-center text-sm ring-1 ring-slate-200">
                Overall score{' '}
                <strong className="text-slate-900">{item.priority_score.toFixed(2)}</strong>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Restock() {
  const queryClient = useQueryClient()
  const [runId, setRunId] = useState(null)
  const [setupOpen, setSetupOpen] = useState(false)
  const [explainOpen, setExplainOpen] = useState(false)
  const [newBudget, setNewBudget] = useState({ period: '', amount: '' })
  const [settings, setSettings] = useState({ budget_id: '', horizon_days: 14, safety: 20 })
  const [error, setError] = useState(null)

  const { data: budgets } = useQuery({ queryKey: ['budgets'], queryFn: () => api.budgets() })
  const { data: config } = useQuery({
    queryKey: ['forecast-config'],
    queryFn: () => api.forecastConfig(),
  })

  const { data: run, isLoading } = useQuery({
    queryKey: ['recommendation-run', runId],
    queryFn: () => (runId ? api.run(runId) : api.latestRun()),
  })

  const createBudget = useMutation({
    mutationFn: (body) => api.createBudget(body),
    onSuccess: (budget) => {
      toast.success('Budget saved.')
      setSettings((s) => ({ ...s, budget_id: String(budget.id) }))
      setNewBudget({ period: '', amount: '' })
      queryClient.invalidateQueries({ queryKey: ['budgets'] })
    },
    onError: (err) => setError(err),
  })

  const generate = useMutation({
    mutationFn: (body) => api.runRecommendations(body),
    onSuccess: (result) => {
      setRunId(result.id)
      setSetupOpen(false)
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['recommendation-run'] })
      toast.success(
        result.budget_constrained
          ? 'Plan ready — the budget does not stretch to everything, so it is ranked.'
          : 'Plan ready — the budget covers everything needed.',
      )
    },
    onError: (err) => setError(err),
  })

  function onGenerate(event) {
    event.preventDefault()
    setError(null)
    if (!settings.budget_id) {
      setError(new Error('Choose or add a budget first.'))
      return
    }
    generate.mutate({
      budget_id: Number(settings.budget_id),
      horizon_days: Number(settings.horizon_days),
      safety_margin_pct: Number(settings.safety) / 100,
      refresh_forecasts: true,
    })
  }

  if (isLoading) return <Spinner label="Loading your restock plan…" />

  const items = run?.items || []
  const decided = items.filter((i) => i.status !== 'proposed').length
  const committed = items
    .filter((i) => i.status === 'accepted' || i.status === 'modified')
    .reduce((sum, i) => sum + (i.operator_quantity ?? 0) * i.unit_cost, 0)

  return (
    <>
      <PageHeader
        title="What to buy"
        subtitle="Where your restocking money will do the most good."
      >
        <button type="button" className="btn-primary" onClick={() => setSetupOpen(true)}>
          <Wallet className="h-4 w-4" aria-hidden />
          {run ? 'New plan' : 'Make a plan'}
        </button>
      </PageHeader>

      {!run ? (
        <Section>
          <EmptyState
            icon={Wallet}
            title="No restock plan yet"
            description="Tell DukaSmart how much you have to spend, and it will work out which products to buy first."
          >
            <button type="button" className="btn-primary" onClick={() => setSetupOpen(true)}>
              Make a plan
            </button>
          </EmptyState>
        </Section>
      ) : (
        <>
          {/* ---------------- Budget summary ---------------- */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Money available" value={money(run.budget_amount)} tone="brand" />
            <Stat
              label="Plan spends"
              value={money(run.total_recommended_cost)}
              sublabel={`${money(run.budget_remaining)} would be left`}
            />
            <Stat
              label="Full top-up would cost"
              value={money(run.total_required_cost)}
              tone={run.budget_constrained ? 'danger' : 'ok'}
              sublabel={
                run.budget_constrained
                  ? `${money(run.budget_shortfall)} short`
                  : 'Budget covers everything'
              }
            />
            <Stat
              label="Decided"
              value={`${decided}/${items.length}`}
              sublabel={`${money(committed)} committed`}
              tone={decided === items.length && items.length > 0 ? 'ok' : 'default'}
            />
          </div>

          <div className="mt-5 card p-5">
            <Meter
              label={`Budget used by this plan`}
              value={run.total_recommended_cost}
              max={run.budget_amount}
              tone={run.budget_constrained ? 'warn' : 'brand'}
            />
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <span>
                Plan made {dateTime(run.generated_at)} for the next {run.horizon_days} days
              </span>
              <span>·</span>
              <span>Safety cushion {Math.round(run.safety_margin_pct * 100)}%</span>
              {run.budget_period && (
                <>
                  <span>·</span>
                  <span>Budget: {run.budget_period}</span>
                </>
              )}
              <button
                type="button"
                className="ml-auto inline-flex items-center gap-1.5 font-medium text-brand-700 hover:underline"
                onClick={() => setExplainOpen(true)}
              >
                <Info className="h-4 w-4" aria-hidden />
                How the order was decided
              </button>
            </div>
          </div>

          {run.budget_constrained && (
            <p className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900 ring-1 ring-amber-200">
              Restocking everything would cost{' '}
              <strong>{money(run.total_required_cost)}</strong> — that is{' '}
              <strong>{money(run.budget_shortfall)}</strong> more than you have. The list below
              is ordered so the most important products are covered first.
            </p>
          )}

          {/* ---------------- The plan ---------------- */}
          <Section
            className="mt-5"
            title="Buy these, in this order"
            description="Accept, change the amount, or skip each one. Nothing is ordered for you."
          >
            {items.length === 0 ? (
              <EmptyState
                title="Nothing needs restocking"
                description="Every product with enough sales history has stock to cover the period ahead."
              />
            ) : (
              <div className="space-y-3">
                {items.map((item) => (
                  <RecommendationCard key={item.id} item={item} rank={item.priority_rank} />
                ))}
              </div>
            )}

            {(run.products_skipped_no_forecast > 0 || run.products_skipped_no_cost > 0) && (
              <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-600 ring-1 ring-slate-200">
                Not included: {run.products_skipped_no_forecast} product(s) without enough sales
                history
                {run.products_skipped_no_cost > 0 &&
                  `, and ${run.products_skipped_no_cost} with no known purchase cost`}
                .
              </p>
            )}
          </Section>
        </>
      )}

      {/* ---------------- Setup modal ---------------- */}
      <Modal
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        title="Make a restock plan"
        description="How much can you spend, and how far ahead should DukaSmart look?"
      >
        <form onSubmit={onGenerate} className="space-y-4">
          <Field label="Money available to spend" required>
            <select
              className="input"
              value={settings.budget_id}
              onChange={(e) => setSettings((s) => ({ ...s, budget_id: e.target.value }))}
            >
              <option value="">Choose a budget…</option>
              {(budgets || []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.period} — {money(b.amount_available)}
                </option>
              ))}
            </select>
          </Field>

          <details className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">
              Add a new budget
            </summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="What is it for">
                <input
                  className="input"
                  placeholder="e.g. September stock"
                  value={newBudget.period}
                  onChange={(e) => setNewBudget((b) => ({ ...b, period: e.target.value }))}
                />
              </Field>
              <Field label="Amount (KES)">
                <input
                  className="input"
                  type="number"
                  min="1"
                  step="1"
                  inputMode="numeric"
                  placeholder="e.g. 25000"
                  value={newBudget.amount}
                  onChange={(e) => setNewBudget((b) => ({ ...b, amount: e.target.value }))}
                />
              </Field>
            </div>
            <button
              type="button"
              className="btn-secondary mt-3 w-full"
              disabled={createBudget.isPending}
              onClick={() => {
                const amount = Number(newBudget.amount)
                if (!newBudget.period.trim()) return toast.error('Give the budget a name.')
                if (!Number.isFinite(amount) || amount <= 0)
                  return toast.error('Enter an amount above zero.')
                createBudget.mutate({
                  period: newBudget.period.trim(),
                  amount_available: amount,
                })
              }}
            >
              {createBudget.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
              Save budget
            </button>
          </details>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Look ahead">
              <select
                className="input"
                value={settings.horizon_days}
                onChange={(e) => setSettings((s) => ({ ...s, horizon_days: e.target.value }))}
              >
                {(config?.allowed_horizons || [7, 14, 30]).map((days) => (
                  <option key={days} value={days}>
                    Next {days} days
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label={`Safety cushion: ${settings.safety}%`}
              hint="Extra stock on top, in case sales run higher than expected."
            >
              <input
                type="range"
                min="0"
                max="60"
                step="5"
                className="mt-3 w-full accent-teal-700"
                value={settings.safety}
                onChange={(e) => setSettings((s) => ({ ...s, safety: Number(e.target.value) }))}
              />
            </Field>
          </div>

          <ErrorNote error={error} />

          <button type="submit" className="btn-primary w-full" disabled={generate.isPending}>
            {generate.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            Work out what to buy
          </button>
          <p className="text-center text-xs text-slate-500">
            The sales outlook is refreshed first, so the plan uses today&rsquo;s numbers.
          </p>
        </form>
      </Modal>

      {/* ---------------- Explanation modal ---------------- */}
      <Modal
        open={explainOpen}
        onClose={() => setExplainOpen(false)}
        title="How the order was decided"
      >
        <div className="space-y-4 text-sm text-slate-700">
          <p>
            If your budget covers everything, every product gets its full top-up and the order
            does not matter.
          </p>
          <p>
            When it does not stretch, DukaSmart scores each product out of 1 on three things and
            works down the list until the money runs out:
          </p>
          <ul className="space-y-2">
            {[
              ['50%', 'How empty the shelf is', 'How much of what you need is missing right now.'],
              ['30%', 'How fast it sells', 'Fast movers earn the money back soonest.'],
              [
                '20%',
                'Profit per shilling spent',
                'How much margin each shilling of stock brings in.',
              ],
            ].map(([weight, title, description]) => (
              <li key={title} className="flex gap-3 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
                <span className="badge-info shrink-0">{weight}</span>
                <span>
                  <strong className="block text-slate-800">{title}</strong>
                  <span className="text-slate-600">{description}</span>
                </span>
              </li>
            ))}
          </ul>
          <p>
            If a product cannot be fully afforded, DukaSmart buys as many as the money allows and
            carries on down the list — a cheaper item further down may still fit.
          </p>
          <p className="rounded-xl bg-brand-50 p-3 text-brand-900 ring-1 ring-brand-200">
            This is advice, not an order. Nothing is bought and no money moves until you do it
            yourself.
          </p>
        </div>
      </Modal>
    </>
  )
}
