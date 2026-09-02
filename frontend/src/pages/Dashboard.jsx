import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CircleSlash,
  PackageSearch,
  ShoppingCart,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { EmptyState, ErrorNote, PageHeader, Section, Spinner, Stat } from '../components/ui'
import { api, money, shortDate, units } from '../lib/api'
import { useAuth } from '../lib/auth'

const chartAxis = { stroke: '#94a3b8', fontSize: 12, tickLine: false, axisLine: false }

function tooltipStyle() {
  return {
    contentStyle: {
      borderRadius: 12,
      border: '1px solid #e2e8f0',
      boxShadow: '0 4px 16px rgba(15,23,42,.08)',
      fontSize: 13,
    },
  }
}

export default function Dashboard() {
  const { user, isOwner } = useAuth()
  const { data, isLoading, error } = useQuery({
    queryKey: ['summary'],
    queryFn: () => api.summary({ horizon_days: 14 }),
  })

  if (isLoading) return <Spinner label="Loading your shop…" />
  if (error) return <ErrorNote error={error} />

  const revenueTrend = data.revenue_change_pct
  const trendUp = revenueTrend != null && revenueTrend >= 0

  const revenueSeries = (data.revenue_by_day || []).map((row) => ({
    ...row,
    label: shortDate(row.date),
  }))

  const firstName = (user?.name || '').split(' ')[0]

  return (
    <>
      <PageHeader
        title={`Habari${firstName ? `, ${firstName}` : ''}`}
        subtitle={`Here is how the shop is doing today, ${shortDate(data.today)}.`}
      >
        <Link to="/sell" className="btn-primary">
          <ShoppingCart className="h-4 w-4" aria-hidden />
          Record a sale
        </Link>
      </PageHeader>

      {/* ---------------- Headline numbers ---------------- */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Sales, last 7 days"
          value={money(data.revenue_last_7_days)}
          sublabel={
            revenueTrend == null
              ? 'No comparison yet'
              : `${trendUp ? 'Up' : 'Down'} ${Math.abs(revenueTrend)}% on the week before`
          }
          icon={trendUp ? TrendingUp : TrendingDown}
          tone={trendUp ? 'ok' : 'warn'}
        />
        <Stat
          label="Products running low"
          value={units(data.running_low_count)}
          sublabel={`Checked against the next ${data.horizon_days} days`}
          icon={AlertTriangle}
          tone={data.running_low_count > 0 ? 'danger' : 'ok'}
        />
        <Stat
          label="Shelves empty"
          value={units(data.out_of_stock_count)}
          sublabel="Nothing left to sell"
          icon={CircleSlash}
          tone={data.out_of_stock_count > 0 ? 'danger' : 'ok'}
        />
        <Stat
          label="Products tracked"
          value={units(data.product_count)}
          sublabel={`${units(data.supplier_count)} suppliers`}
          icon={Boxes}
          tone="brand"
        />
      </div>

      {/* ---------------- Charts ---------------- */}
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Section
          title="Money coming in"
          description="Daily sales over the last 30 days"
          className="lg:col-span-2"
        >
          {revenueSeries.length === 0 ? (
            <EmptyState
              icon={ShoppingCart}
              title="No sales recorded yet"
              description="Record your first sale and this chart will fill in."
            />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={revenueSeries} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0d9488" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#0d9488" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="label" {...chartAxis} minTickGap={24} />
                  <YAxis
                    {...chartAxis}
                    width={52}
                    tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)}
                  />
                  <Tooltip
                    {...tooltipStyle()}
                    formatter={(value) => [money(value), 'Sales']}
                    labelFormatter={(label) => label}
                  />
                  <Area
                    type="monotone"
                    dataKey="revenue"
                    stroke="#0d9488"
                    strokeWidth={2.5}
                    fill="url(#revFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>

        <Section title="Best sellers" description="Units sold in the last 7 days">
          {(data.top_sellers || []).length === 0 ? (
            <EmptyState icon={PackageSearch} title="Nothing sold this week yet" />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.top_sellers}
                  layout="vertical"
                  margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" {...chartAxis} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    {...chartAxis}
                    width={104}
                    tickFormatter={(v) => (v.length > 15 ? `${v.slice(0, 14)}…` : v)}
                  />
                  <Tooltip {...tooltipStyle()} formatter={(value) => [units(value), 'Units']} />
                  <Bar dataKey="units" fill="#14b8a6" radius={[0, 6, 6, 0]} barSize={18} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>
      </div>

      {/* ---------------- Running low ---------------- */}
      <Section
        className="mt-5"
        title="Products running low"
        description={`Expected to sell more than you have over the next ${data.horizon_days} days`}
        action={
          isOwner && (
            <Link to="/restock" className="btn-primary !py-2 !text-xs">
              <Wallet className="h-4 w-4" aria-hidden />
              Plan a restock
            </Link>
          )
        }
      >
        {(data.running_low || []).length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="Nothing is running low"
            description={
              data.forecasts_available === 0
                ? 'No sales outlook has been worked out yet. Open Sales outlook and press Update.'
                : 'Every product has enough stock for the period ahead.'
            }
          >
            {data.forecasts_available === 0 && (
              <Link to="/forecasts" className="btn-secondary">
                Go to Sales outlook
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            )}
          </EmptyState>
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.running_low.map((row) => (
              <li key={row.product_id} className="flex items-center gap-4 py-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-rose-100 text-rose-700">
                  <AlertTriangle className="h-5 w-5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-slate-900">{row.name}</p>
                  <p className="truncate text-sm text-slate-500">{row.reason}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-sm font-bold text-slate-900">{units(row.current_stock)} left</p>
                  <p className="text-xs text-rose-600">
                    short {units(row.estimated_shortage)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {data.insufficient_history_count > 0 && (
        <p className="mt-4 rounded-xl bg-sky-50 p-4 text-sm text-sky-900 ring-1 ring-sky-200">
          <strong>{data.insufficient_history_count}</strong>{' '}
          {data.insufficient_history_count === 1 ? 'product does' : 'products do'} not have enough
          sales history yet, so DukaSmart will not guess their outlook. Keep recording sales and
          they will be included automatically.
        </p>
      )}
    </>
  )
}
