import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BarChart3, Target, Truck, Wallet } from 'lucide-react'
import {
  EmptyState,
  ErrorNote,
  PageHeader,
  Section,
  Spinner,
  Stat,
  TableWrap,
} from '../components/ui'
import { api, dateTime, longDate, money, shortDate, units } from '../lib/api'
import { useAuth } from '../lib/auth'

const chartAxis = { stroke: '#94a3b8', fontSize: 12, tickLine: false, axisLine: false }
const tooltipStyle = { borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 13 }

const isoDaysAgo = (days) => {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}
const todayISO = () => new Date().toISOString().slice(0, 10)

function DateRange({ start, end, onChange }) {
  return (
    <div className="mb-5 flex flex-wrap items-end gap-3">
      <div>
        <label className="label">From</label>
        <input
          className="input !w-auto"
          type="date"
          value={start}
          max={end}
          onChange={(e) => onChange({ start: e.target.value, end })}
        />
      </div>
      <div>
        <label className="label">To</label>
        <input
          className="input !w-auto"
          type="date"
          value={end}
          min={start}
          max={todayISO()}
          onChange={(e) => onChange({ start, end: e.target.value })}
        />
      </div>
      <div className="flex gap-2">
        {[
          [7, '7 days'],
          [30, '30 days'],
          [90, '90 days'],
        ].map(([days, label]) => (
          <button
            key={days}
            type="button"
            className="btn-secondary !px-3 !py-2 !text-xs"
            onClick={() => onChange({ start: isoDaysAgo(days - 1), end: todayISO() })}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
function SalesReport() {
  const [range, setRange] = useState({ start: isoDaysAgo(29), end: todayISO() })
  const { data, isLoading, error } = useQuery({
    queryKey: ['report-sales', range],
    queryFn: () => api.salesReport(range),
  })

  if (isLoading) return <Spinner />
  if (error) return <ErrorNote error={error} />

  const daily = (data.by_day || []).map((row) => ({ ...row, label: shortDate(row.date) }))
  // by_product already arrives sorted most-profitable-first (see the backend
  // report), which is exactly the order useful for "what should I push?".
  const profitChart = data.by_product.slice(0, 8).map((row) => ({
    name: row.name,
    profit: row.profit,
  }))

  return (
    <>
      <DateRange {...range} onChange={setRange} />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Money taken" value={money(data.total_revenue)} tone="ok" />
        <Stat
          label="Profit"
          value={money(data.total_profit)}
          sublabel={
            data.overall_margin_pct == null ? undefined : `${data.overall_margin_pct}% margin`
          }
          tone={data.total_profit >= 0 ? 'ok' : 'danger'}
        />
        <Stat label="Units sold" value={units(data.total_units)} />
        <Stat label="Number of sales" value={units(data.sale_count)} />
      </div>

      {daily.length > 0 && (
        <Section title="Money coming in" description="Sales by day" className="mb-5">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="label" {...chartAxis} minTickGap={24} />
                <YAxis
                  {...chartAxis}
                  width={52}
                  tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)}
                />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [money(v), 'Sales']} />
                <Bar dataKey="revenue" fill="#0d9488" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}

      {profitChart.length > 0 && (
        <Section
          title="Most profitable products"
          description="Revenue minus what the stock cost to buy, for this period"
          className="mb-5"
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={profitChart}
                layout="vertical"
                margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" {...chartAxis} tickFormatter={(v) => money(v)} />
                <YAxis
                  type="category"
                  dataKey="name"
                  {...chartAxis}
                  width={112}
                  tickFormatter={(v) => (v.length > 16 ? `${v.slice(0, 15)}…` : v)}
                />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [money(v), 'Profit']} />
                <Bar dataKey="profit" radius={[0, 6, 6, 0]} barSize={18}>
                  {profitChart.map((row) => (
                    <Cell key={row.name} fill={row.profit >= 0 ? '#14b8a6' : '#e11d48'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}

      {data.by_product.length === 0 ? (
        <EmptyState title="No sales in this period" />
      ) : (
        <TableWrap>
          <table className="min-w-full divide-y divide-slate-200 bg-white">
            <thead className="bg-slate-50">
              <tr>
                <th className="th">Product</th>
                <th className="th text-right">Units sold</th>
                <th className="th text-right">Money taken</th>
                <th className="th hidden text-right sm:table-cell">Cost of goods</th>
                <th className="th text-right">Profit</th>
                <th className="th hidden text-right sm:table-cell">Margin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.by_product.map((row) => (
                <tr key={row.product_id}>
                  <td className="td font-medium text-slate-800">{row.name}</td>
                  <td className="td text-right">{units(row.units_sold)}</td>
                  <td className="td text-right font-medium">{money(row.revenue)}</td>
                  <td className="td hidden text-right text-slate-500 sm:table-cell">
                    {money(row.cost_of_goods_sold)}
                  </td>
                  <td
                    className={`td text-right font-semibold ${
                      row.profit >= 0 ? 'text-emerald-700' : 'text-rose-700'
                    }`}
                  >
                    {money(row.profit)}
                  </td>
                  <td className="td hidden text-right text-slate-500 sm:table-cell">
                    {row.margin_pct == null ? '—' : `${row.margin_pct}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </>
  )
}

// --------------------------------------------------------------------------
function PurchasesReport() {
  const [range, setRange] = useState({ start: isoDaysAgo(29), end: todayISO() })
  const { data, isLoading, error } = useQuery({
    queryKey: ['report-purchases', range],
    queryFn: () => api.purchasesReport(range),
  })

  if (isLoading) return <Spinner />
  if (error) return <ErrorNote error={error} />

  return (
    <>
      <DateRange {...range} onChange={setRange} />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Money spent" value={money(data.total_spend)} tone="brand" />
        <Stat label="Units received" value={units(data.total_units)} />
        <Stat label="Deliveries" value={units(data.purchase_count)} />
        <Stat label="Suppliers used" value={units(data.by_supplier.length)} />
      </div>

      {data.by_supplier.length > 0 && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.by_supplier.map((row) => (
            <div key={row.supplier} className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <p className="truncate text-sm font-medium text-slate-800">{row.supplier}</p>
              <p className="mt-1 text-xl font-bold text-slate-900">{money(row.spend)}</p>
              <p className="text-xs text-slate-500">{units(row.deliveries)} deliveries</p>
            </div>
          ))}
        </div>
      )}

      {data.by_product.length === 0 ? (
        <EmptyState icon={Truck} title="No deliveries in this period" />
      ) : (
        <TableWrap>
          <table className="min-w-full divide-y divide-slate-200 bg-white">
            <thead className="bg-slate-50">
              <tr>
                <th className="th">Product</th>
                <th className="th text-right">Units received</th>
                <th className="th text-right">Money spent</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.by_product.map((row) => (
                <tr key={row.product_id}>
                  <td className="td font-medium text-slate-800">{row.name}</td>
                  <td className="td text-right">{units(row.units_received)}</td>
                  <td className="td text-right font-medium">{money(row.spend)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </>
  )
}

// --------------------------------------------------------------------------
function AccuracyReport() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['report-accuracy'],
    queryFn: () => api.forecastAccuracy(),
  })

  if (isLoading) return <Spinner />
  if (error) return <ErrorNote error={error} />

  if (data.evaluated_count === 0) {
    return (
      <EmptyState
        icon={Target}
        title="Nothing to score yet"
        description={
          data.pending_count > 0
            ? `${data.pending_count} forecast(s) are still running — a forecast can only be scored once the days it covers have actually passed.`
            : 'Once forecasts have been made and the period they cover has passed, their accuracy shows up here.'
        }
      />
    )
  }

  const chart = data.rows.slice(0, 12).map((row) => ({
    name: row.product_name,
    predicted: row.predicted_quantity,
    actual: row.actual_quantity,
  }))

  return (
    <>
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Forecasts scored" value={units(data.evaluated_count)} />
        <Stat label="Still running" value={units(data.pending_count)} />
        <Stat
          label="Typical miss"
          value={data.mae == null ? '—' : `${data.mae.toFixed(1)} units`}
          tone="brand"
        />
        <Stat
          label="Typical miss (%)"
          value={data.mape == null ? '—' : `${data.mape.toFixed(0)}%`}
        />
      </div>

      <div className="mb-5 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chart} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis
              dataKey="name"
              {...chartAxis}
              tickFormatter={(v) => (v.length > 10 ? `${v.slice(0, 9)}…` : v)}
              interval={0}
              angle={-25}
              textAnchor="end"
              height={64}
            />
            <YAxis {...chartAxis} width={40} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="predicted" name="Expected" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            <Bar dataKey="actual" name="Actually sold" fill="#0d9488" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <TableWrap>
        <table className="min-w-full divide-y divide-slate-200 bg-white">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Product</th>
              <th className="th hidden sm:table-cell">Period covered</th>
              <th className="th text-right">Expected</th>
              <th className="th text-right">Sold</th>
              <th className="th text-right">Off by</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.rows.map((row) => (
              <tr key={row.forecast_id}>
                <td className="td font-medium text-slate-800">{row.product_name}</td>
                <td className="td hidden text-xs text-slate-500 sm:table-cell">
                  {shortDate(row.window_start)} – {shortDate(row.window_end)}
                </td>
                <td className="td text-right">{units(row.predicted_quantity)}</td>
                <td className="td text-right font-medium">{units(row.actual_quantity)}</td>
                <td className="td text-right">
                  <span
                    className={
                      row.percentage_error == null
                        ? 'badge-muted'
                        : row.percentage_error <= 20
                          ? 'badge-ok'
                          : row.percentage_error <= 50
                            ? 'badge-warn'
                            : 'badge-danger'
                    }
                  >
                    {units(row.absolute_error)}
                    {row.percentage_error != null && ` (${row.percentage_error.toFixed(0)}%)`}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </>
  )
}

// --------------------------------------------------------------------------
function FollowThroughReport() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['report-follow-through'],
    queryFn: () => api.followThrough(),
  })

  if (isLoading) return <Spinner />
  if (error) return <ErrorNote error={error} />

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={Wallet}
        title="No restock plans yet"
        description="Once you have made a plan, this shows what was suggested against what you actually bought."
      />
    )
  }

  const STATUS = {
    proposed: ['badge-muted', 'Not decided'],
    accepted: ['badge-ok', 'Accepted'],
    modified: ['badge-info', 'Changed'],
    rejected: ['badge-danger', 'Skipped'],
  }

  return (
    <TableWrap>
      <table className="min-w-full divide-y divide-slate-200 bg-white">
        <thead className="bg-slate-50">
          <tr>
            <th className="th">Product</th>
            <th className="th hidden sm:table-cell">Plan made</th>
            <th className="th text-right">Suggested</th>
            <th className="th text-right">Your decision</th>
            <th className="th text-right">Actually bought</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.map((row) => {
            const [badge, label] = STATUS[row.status] || STATUS.proposed
            return (
              <tr key={`${row.run_id}-${row.product_id}`}>
                <td className="td font-medium text-slate-800">{row.product_name}</td>
                <td className="td hidden whitespace-nowrap text-xs text-slate-500 sm:table-cell">
                  {dateTime(row.generated_at)}
                </td>
                <td className="td text-right">
                  {units(row.recommended_quantity)}
                  <span className="block text-xs text-slate-400">
                    {money(row.recommended_cost)}
                  </span>
                </td>
                <td className="td text-right">
                  <span className={badge}>{label}</span>
                  {row.operator_quantity != null && (
                    <span className="mt-1 block text-xs text-slate-500">
                      {units(row.operator_quantity)} units
                    </span>
                  )}
                </td>
                <td className="td text-right font-medium">
                  {units(row.actually_purchased_quantity)}
                  <span className="block text-xs text-slate-400">
                    {money(row.actually_purchased_cost)}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </TableWrap>
  )
}

// --------------------------------------------------------------------------
export default function Reports() {
  const { isOwner } = useAuth()
  const [tab, setTab] = useState('sales')

  const tabs = [
    ['sales', 'Sales'],
    ['purchases', 'Deliveries'],
    ['accuracy', 'How good were the predictions'],
    ...(isOwner ? [['follow', 'Plans vs. what you bought']] : []),
  ]

  return (
    <>
      <PageHeader title="Reports" subtitle="How the shop has been doing, and how well DukaSmart has been advising you." />

      <div className="scroll-x mb-5 -mx-4 px-4 sm:mx-0 sm:px-0">
        <div className="inline-flex gap-1 rounded-xl bg-slate-200 p-1">
          {tabs.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                tab === key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <Section
        title={
          tab === 'accuracy'
            ? 'Predicted vs. actually sold'
            : tab === 'follow'
              ? 'What was suggested, and what you bought'
              : undefined
        }
        description={
          tab === 'accuracy'
            ? 'Only forecasts whose period has already passed can be scored.'
            : tab === 'follow'
              ? 'Deliveries recorded on or after the plan date are counted as follow-through.'
              : undefined
        }
      >
        {tab === 'sales' && <SalesReport />}
        {tab === 'purchases' && <PurchasesReport />}
        {tab === 'accuracy' && <AccuracyReport />}
        {tab === 'follow' && <FollowThroughReport />}
      </Section>

      {tab === 'sales' && (
        <p className="mt-4 flex items-center gap-2 text-xs text-slate-500">
          <BarChart3 className="h-4 w-4" aria-hidden />
          Figures come straight from recorded sales and deliveries — nothing is estimated here.
        </p>
      )}
    </>
  )
}
