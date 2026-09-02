import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CircleHelp, Info, LineChart as LineChartIcon, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import {
  EmptyState,
  ErrorNote,
  Modal,
  PageHeader,
  Section,
  Spinner,
  TableWrap,
} from '../components/ui'
import { api, shortDate, units } from '../lib/api'
import { useAuth } from '../lib/auth'

/** Technical model names never reach the operator. */
const MODEL_LABEL = {
  weighted_moving_average: 'Recent average',
  simple_exponential_smoothing: 'Smoothed trend',
  gradient_boosting: 'Pattern learner',
}

const chartAxis = { stroke: '#94a3b8', fontSize: 12, tickLine: false, axisLine: false }

/** History + projection for one product, plotted on a single continuous line. */
function ForecastDetail({ product, horizon, onClose }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['forecast-detail', product?.product_id, horizon],
    queryFn: () => api.productForecast(product.product_id, { horizon_days: horizon }),
    enabled: Boolean(product),
  })

  // Show the last 60 days of history so the projection is readable next to it.
  const history = (data?.history || []).slice(-60)
  const projected = data?.projected || []
  const joinDate = history.length ? history[history.length - 1].date : null

  const series = [
    ...history.map((row) => ({
      date: row.date,
      label: shortDate(row.date),
      actual: row.quantity,
      expected: row.date === joinDate ? row.quantity : null,
    })),
    ...projected.map((row) => ({
      date: row.date,
      label: shortDate(row.date),
      actual: null,
      expected: row.quantity,
    })),
  ]

  const forecast = data?.forecast

  return (
    <Modal
      open={Boolean(product)}
      onClose={onClose}
      wide
      title={product?.name}
      description="What you have sold, and what DukaSmart expects next."
    >
      {isLoading && <Spinner />}
      <ErrorNote error={error} />

      {data && (
        <>
          {series.length > 0 ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="label" {...chartAxis} minTickGap={28} />
                  <YAxis {...chartAxis} width={40} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 12,
                      border: '1px solid #e2e8f0',
                      fontSize: 13,
                    }}
                    formatter={(value, name) => [`${Number(value).toFixed(1)} units`, name]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {joinDate && (
                    <ReferenceLine
                      x={shortDate(joinDate)}
                      stroke="#94a3b8"
                      strokeDasharray="4 4"
                      label={{ value: 'today', position: 'top', fontSize: 11, fill: '#64748b' }}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="actual"
                    name="Sold"
                    stroke="#0f766e"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="expected"
                    name="Expected"
                    stroke="#f59e0b"
                    strokeWidth={2.5}
                    strokeDasharray="5 4"
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState title="No sales history yet" />
          )}

          {forecast && forecast.data_sufficiency_flag === 'sufficient' ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Expected over {forecast.horizon_days} days
                </p>
                <p className="mt-1 text-2xl font-bold text-slate-900">
                  {units(forecast.predicted_quantity)}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <p className="text-xs uppercase tracking-wide text-slate-500">Method chosen</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">
                  {MODEL_LABEL[forecast.model_used] || forecast.model_used}
                </p>
                <p className="text-xs text-slate-500">
                  Beat {(forecast.candidate_scores?.length || 1) - 1} other method(s) on past data
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <p className="text-xs uppercase tracking-wide text-slate-500">Typical daily miss</p>
                <p className="mt-1 text-2xl font-bold text-slate-900">
                  {forecast.mae?.toFixed(1)}
                </p>
                <p className="text-xs text-slate-500">
                  units {forecast.mape != null && `· about ${forecast.mape.toFixed(0)}% off`}
                </p>
              </div>
            </div>
          ) : (
            forecast && (
              <p className="mt-5 rounded-xl bg-sky-50 p-4 text-sm text-sky-900 ring-1 ring-sky-200">
                {forecast.insufficiency_reason}
              </p>
            )
          )}

          {/* Reproducibility panel — exactly what went into this number. */}
          {forecast?.data_window_start && (
            <details className="mt-4 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <summary className="cursor-pointer text-sm font-medium text-slate-700">
                How this was worked out
              </summary>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-500">Sales history used</dt>
                  <dd className="font-medium text-slate-800">
                    {shortDate(forecast.data_window_start)} to {shortDate(forecast.data_window_end)}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Days of data</dt>
                  <dd className="font-medium text-slate-800">
                    {forecast.observations_used} ({forecast.nonzero_observations} with a sale)
                  </dd>
                </div>
              </dl>
              {forecast.candidate_scores?.length > 0 && (
                <>
                  <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Methods compared (lower miss is better)
                  </p>
                  <ul className="mt-2 space-y-1 text-sm">
                    {forecast.candidate_scores.map((score) => (
                      <li
                        key={score.model}
                        className={`flex justify-between rounded-lg px-2 py-1 ${
                          score.model === forecast.model_used
                            ? 'bg-brand-100 font-semibold text-brand-900'
                            : 'text-slate-600'
                        }`}
                      >
                        <span>{MODEL_LABEL[score.model] || score.model}</span>
                        <span className="font-mono">
                          {score.mae == null ? 'could not fit' : score.mae.toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </details>
          )}
        </>
      )}
    </Modal>
  )
}

export default function Forecasts() {
  const { isOwner } = useAuth()
  const queryClient = useQueryClient()
  const [horizon, setHorizon] = useState(14)
  const [detailFor, setDetailFor] = useState(null)
  const [explainOpen, setExplainOpen] = useState(false)

  const { data: config } = useQuery({
    queryKey: ['forecast-config'],
    queryFn: () => api.forecastConfig(),
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['risk', horizon],
    queryFn: () => api.stockRisk({ horizon_days: horizon }),
  })

  const run = useMutation({
    mutationFn: () => api.runForecasts({ horizon_days: horizon }),
    onSuccess: (forecasts) => {
      const ready = forecasts.filter((f) => f.data_sufficiency_flag === 'sufficient').length
      toast.success(`Outlook updated for ${ready} of ${forecasts.length} products.`)
      queryClient.invalidateQueries()
    },
    onError: (err) => toast.error(err.message),
  })

  if (isLoading) return <Spinner label="Working out the outlook…" />
  if (error) return <ErrorNote error={error} />

  const rows = data || []
  const lowRows = rows.filter((r) => r.at_risk)
  const fineRows = rows.filter((r) => !r.at_risk && r.status === 'Stock is fine')
  const unknownRows = rows.filter((r) => !r.at_risk && r.status !== 'Stock is fine')

  return (
    <>
      <PageHeader
        title="Sales outlook"
        subtitle="How much of each product you are likely to sell next, and whether you have enough."
      >
        <select
          className="input !w-auto !py-2"
          value={horizon}
          onChange={(e) => setHorizon(Number(e.target.value))}
          aria-label="Period to look ahead"
        >
          {(config?.allowed_horizons || [7, 14, 30]).map((days) => (
            <option key={days} value={days}>
              Next {days} days
            </option>
          ))}
        </select>
        {isOwner && (
          <button
            type="button"
            className="btn-primary"
            onClick={() => run.mutate()}
            disabled={run.isPending}
          >
            {run.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="h-4 w-4" aria-hidden />
            )}
            Update outlook
          </button>
        )}
      </PageHeader>

      <button
        type="button"
        onClick={() => setExplainOpen(true)}
        className="mb-5 flex w-full items-center gap-3 rounded-xl bg-sky-50 p-4 text-left text-sm text-sky-900 ring-1 ring-sky-200 hover:bg-sky-100"
      >
        <Info className="h-5 w-5 shrink-0" aria-hidden />
        <span className="flex-1">
          DukaSmart only predicts where there is enough sales history to be honest about it.
        </span>
        <CircleHelp className="h-5 w-5 shrink-0 text-sky-600" aria-hidden />
      </button>

      {rows.length === 0 ? (
        <Section>
          <EmptyState
            icon={LineChartIcon}
            title="No outlook yet"
            description="Press 'Update outlook' to work out what you are likely to sell next."
          />
        </Section>
      ) : (
        <div className="space-y-5">
          {lowRows.length > 0 && (
            <Section
              title="Running low"
              description="You are likely to sell more than you have on the shelf."
            >
              <RiskTable rows={lowRows} onPick={setDetailFor} tone="danger" />
            </Section>
          )}

          {fineRows.length > 0 && (
            <Section title="Enough stock" description="Covered for the period ahead.">
              <RiskTable rows={fineRows} onPick={setDetailFor} tone="ok" />
            </Section>
          )}

          {unknownRows.length > 0 && (
            <Section
              title="Not enough history yet"
              description="These are not predicted. Keep recording sales and they will be included automatically."
            >
              <ul className="divide-y divide-slate-100">
                {unknownRows.map((row) => (
                  <li key={row.product_id} className="flex items-start gap-3 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-slate-800">{row.name}</p>
                      <p className="text-sm text-slate-500">{row.reason}</p>
                    </div>
                    <span className="badge-muted shrink-0">{units(row.current_stock)} on shelf</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>
      )}

      <ForecastDetail product={detailFor} horizon={horizon} onClose={() => setDetailFor(null)} />

      <Modal
        open={explainOpen}
        onClose={() => setExplainOpen(false)}
        title="How the outlook works"
      >
        <div className="space-y-4 text-sm text-slate-700">
          <p>
            DukaSmart looks at how many units of each product you sold on every day since you
            started recording, including the days you sold none.
          </p>
          <p>
            <strong>It only predicts when it has enough to go on.</strong> A product needs at
            least {config?.min_nonzero_observations ?? 10} days with a sale, across at least{' '}
            {config?.min_history_days ?? 28} days of history. Below that, DukaSmart says
            &ldquo;not enough history&rdquo; rather than guessing.
          </p>
          <p>
            When there is enough, three different methods compete. Each one is tested by hiding
            the most recent {config?.holdout_days ?? 14} days, predicting them, and checking how
            close it got. Whichever came closest for <em>that</em> product is the one used.
          </p>
          <p className="rounded-xl bg-slate-50 p-3 text-slate-600 ring-1 ring-slate-200">
            Tap any product to see its sales history, its projection, and which methods were tried.
          </p>
        </div>
      </Modal>
    </>
  )
}

function RiskTable({ rows, onPick, tone }) {
  return (
    <TableWrap>
      <table className="min-w-full divide-y divide-slate-200 bg-white">
        <thead className="bg-slate-50">
          <tr>
            <th className="th">Product</th>
            <th className="th text-right">On shelf</th>
            <th className="th text-right">Likely to sell</th>
            <th className="th hidden text-right sm:table-cell">Days of cover</th>
            <th className="th text-right">{tone === 'danger' ? 'Short by' : 'Status'}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr
              key={row.product_id}
              className="cursor-pointer hover:bg-slate-50"
              onClick={() => onPick(row)}
            >
              <td className="td">
                <span className="font-medium text-slate-900">{row.name}</span>
                <span className="block font-mono text-xs text-slate-400">{row.sku}</span>
              </td>
              <td className="td text-right font-medium">{units(row.current_stock)}</td>
              <td className="td text-right">{units(row.forecast_demand)}</td>
              <td className="td hidden text-right text-slate-500 sm:table-cell">
                {row.days_of_cover == null ? '—' : `${row.days_of_cover.toFixed(0)} days`}
              </td>
              <td className="td text-right">
                {tone === 'danger' ? (
                  <span className="badge-danger">{units(row.estimated_shortage)}</span>
                ) : (
                  <span className="badge-ok">Fine</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  )
}
