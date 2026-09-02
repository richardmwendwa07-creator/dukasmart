import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList, ShoppingCart, Truck } from 'lucide-react'
import { EmptyState, ErrorNote, PageHeader, Section, Spinner } from '../components/ui'
import { api, longDate, money, units } from '../lib/api'

function TransactionList({ rows, kind }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={kind === 'sales' ? ShoppingCart : Truck}
        title={kind === 'sales' ? 'No sales recorded yet' : 'No deliveries recorded yet'}
      />
    )
  }

  return (
    <ul className="space-y-3">
      {rows.map((row) => {
        const isSale = kind === 'sales'
        const total = isSale ? row.total_amount : row.total_cost
        const when = isSale ? row.date : row.date_received
        return (
          <li key={row.id} className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-slate-900">
                  {longDate(when)}
                  <span className="ml-2 font-mono text-xs font-normal text-slate-400">
                    #{row.id}
                  </span>
                </p>
                <p className="text-sm text-slate-500">
                  {isSale
                    ? `${row.items.length} product${row.items.length === 1 ? '' : 's'}`
                    : `From ${row.supplier_name || 'unknown supplier'}`}
                  {row.note ? ` · ${row.note}` : ''}
                </p>
              </div>
              <p
                className={`text-lg font-bold ${isSale ? 'text-emerald-700' : 'text-slate-900'}`}
              >
                {isSale ? '+' : '−'}
                {money(total)}
              </p>
            </div>

            <ul className="mt-3 divide-y divide-slate-100 border-t border-slate-100 pt-2">
              {row.items.map((item) => (
                <li key={item.id} className="flex justify-between gap-3 py-1.5 text-sm">
                  <span className="text-slate-700">
                    {item.product_name}
                    <span className="ml-2 text-slate-400">
                      ×{units(isSale ? item.quantity : item.quantity_received)}
                    </span>
                  </span>
                  <span className="shrink-0 font-medium text-slate-600">
                    {money(item.line_total)}
                  </span>
                </li>
              ))}
            </ul>
          </li>
        )
      })}
    </ul>
  )
}

export default function History() {
  const [tab, setTab] = useState('sales')

  const sales = useQuery({ queryKey: ['sales'], queryFn: () => api.sales({ limit: 100 }) })
  const purchases = useQuery({
    queryKey: ['purchases'],
    queryFn: () => api.purchases({ limit: 100 }),
  })

  const active = tab === 'sales' ? sales : purchases

  return (
    <>
      <PageHeader
        title="Sales & deliveries"
        subtitle="Everything that has been recorded, newest first."
      />

      <div className="mb-5 inline-flex rounded-xl bg-slate-200 p-1">
        {[
          ['sales', 'Sales', ShoppingCart],
          ['purchases', 'Deliveries', Truck],
        ].map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
              tab === key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'
            }`}
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      <Section>
        {active.isLoading && <Spinner />}
        <ErrorNote error={active.error} />
        {active.data && (
          <>
            {active.data.length >= 100 && (
              <p className="mb-3 flex items-center gap-2 text-xs text-slate-500">
                <ClipboardList className="h-4 w-4" aria-hidden />
                Showing the 100 most recent.
              </p>
            )}
            <TransactionList rows={active.data} kind={tab} />
          </>
        )}
      </Section>
    </>
  )
}
