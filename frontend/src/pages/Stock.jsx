import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight, History, Loader2, Search, SlidersHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import {
  EmptyState,
  ErrorNote,
  Field,
  Modal,
  PageHeader,
  Section,
  Spinner,
  Stat,
  TableWrap,
} from '../components/ui'
import { api, dateTime, money, units } from '../lib/api'

const SOURCE_LABEL = {
  sale: 'Sold',
  purchase: 'Delivery',
  adjustment: 'Correction',
}

function StockBadge({ value }) {
  if (value <= 0) return <span className="badge-danger">Empty</span>
  if (value <= 5) return <span className="badge-warn">Very low</span>
  return <span className="badge-ok">{units(value)}</span>
}

/** The per-product audit trail: every movement that produced the current count. */
function MovementHistory({ product, onClose }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['movements', product?.product_id],
    queryFn: () => api.movements({ product_id: product.product_id, limit: 300 }),
    enabled: Boolean(product),
  })

  return (
    <Modal
      open={Boolean(product)}
      onClose={onClose}
      wide
      title={product?.name}
      description="Every change to this product's shelf count, newest first."
    >
      {isLoading && <Spinner />}
      <ErrorNote error={error} />
      {data && data.length === 0 && (
        <EmptyState icon={History} title="No movements yet" />
      )}
      {data && data.length > 0 && (
        <TableWrap>
          <table className="min-w-full divide-y divide-slate-200 bg-white">
            <thead className="bg-slate-50">
              <tr>
                <th className="th">When</th>
                <th className="th">What happened</th>
                <th className="th text-right">Change</th>
                <th className="th text-right">Left after</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((m) => (
                <tr key={m.id}>
                  <td className="td whitespace-nowrap text-slate-500">{dateTime(m.timestamp)}</td>
                  <td className="td">
                    <span className="font-medium text-slate-800">
                      {SOURCE_LABEL[m.source_type] || m.source_type}
                    </span>
                    {m.note && <span className="block text-xs text-slate-500">{m.note}</span>}
                  </td>
                  <td
                    className={`td whitespace-nowrap text-right font-semibold ${
                      m.change_qty > 0 ? 'text-emerald-700' : 'text-rose-700'
                    }`}
                  >
                    <span className="inline-flex items-center gap-1">
                      {m.change_qty > 0 ? (
                        <ArrowUpRight className="h-4 w-4" aria-hidden />
                      ) : (
                        <ArrowDownRight className="h-4 w-4" aria-hidden />
                      )}
                      {m.change_qty > 0 ? '+' : ''}
                      {units(m.change_qty)}
                    </span>
                  </td>
                  <td className="td text-right font-mono text-slate-900">
                    {units(m.resulting_stock)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
      <p className="mt-4 text-xs text-slate-500">
        The shelf count is always the sum of these changes — it is never edited directly.
      </p>
    </Modal>
  )
}

/** Stock-take correction / breakage write-off. */
function AdjustModal({ product, onClose }) {
  const queryClient = useQueryClient()
  const [change, setChange] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)

  const mutation = useMutation({
    mutationFn: (body) => api.createAdjustment(body),
    onSuccess: () => {
      toast.success('Shelf count corrected.')
      queryClient.invalidateQueries()
      onClose()
    },
    onError: (err) => setError(err),
  })

  function onSubmit(event) {
    event.preventDefault()
    setError(null)
    const value = Number(change)
    if (!Number.isInteger(value) || value === 0) {
      setError(new Error('Enter a whole number — positive to add, negative to remove.'))
      return
    }
    if (!note.trim()) {
      setError(new Error('Say why the count changed, so the history makes sense later.'))
      return
    }
    mutation.mutate({
      product_id: product.product_id,
      change_qty: value,
      note: note.trim(),
    })
  }

  const preview = product ? product.current_stock + (Number(change) || 0) : 0

  return (
    <Modal
      open={Boolean(product)}
      onClose={onClose}
      title="Correct the shelf count"
      description={product ? `${product.name} — currently ${units(product.current_stock)}` : ''}
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="How many units to add or remove"
          required
          hint="Use a minus sign to remove, e.g. -3 for three broken items."
        >
          <input
            className="input"
            type="number"
            step="1"
            inputMode="numeric"
            value={change}
            onChange={(e) => setChange(e.target.value)}
            placeholder="e.g. -3"
          />
        </Field>
        <Field label="Reason" required>
          <input
            className="input"
            value={note}
            maxLength={255}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Two bottles broke, one expired"
          />
        </Field>

        {change !== '' && Number.isInteger(Number(change)) && Number(change) !== 0 && (
          <p
            className={`rounded-xl p-3 text-sm ${
              preview < 0
                ? 'bg-rose-50 text-rose-800 ring-1 ring-rose-200'
                : 'bg-slate-50 text-slate-700 ring-1 ring-slate-200'
            }`}
          >
            New shelf count will be <strong>{units(preview)}</strong>
            {preview < 0 && ' — that is below zero, so it will be rejected.'}
          </p>
        )}

        <ErrorNote error={error} />

        <div className="flex gap-2">
          <button type="button" className="btn-secondary flex-1" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary flex-1" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            Save correction
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function StockPage() {
  const [search, setSearch] = useState('')
  const [historyFor, setHistoryFor] = useState(null)
  const [adjustFor, setAdjustFor] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['stock'],
    queryFn: () => api.stock(),
  })

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase()
    const list = data || []
    if (!term) return list
    return list.filter(
      (r) =>
        r.name.toLowerCase().includes(term) ||
        r.sku.toLowerCase().includes(term) ||
        (r.category || '').toLowerCase().includes(term),
    )
  }, [data, search])

  if (isLoading) return <Spinner label="Counting stock…" />
  if (error) return <ErrorNote error={error} />

  const totalValue = (data || []).reduce((sum, r) => sum + r.stock_value_at_cost, 0)
  const empty = (data || []).filter((r) => r.current_stock <= 0).length
  const totalUnits = (data || []).reduce((sum, r) => sum + r.current_stock, 0)

  return (
    <>
      <PageHeader
        title="Stock"
        subtitle="What is on the shelf right now, worked out from every sale and delivery you have recorded."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Products" value={units((data || []).length)} />
        <Stat label="Units on hand" value={units(totalUnits)} />
        <Stat label="Stock value (at cost)" value={money(totalValue)} tone="brand" />
        <Stat label="Empty shelves" value={units(empty)} tone={empty ? 'danger' : 'ok'} />
      </div>

      <Section className="mt-5">
        <div className="relative mb-4">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
            aria-hidden
          />
          <input
            className="input !pl-11"
            placeholder="Search by name, code, or category"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {rows.length === 0 ? (
          <EmptyState title="Nothing matches that search" />
        ) : (
          <TableWrap>
            <table className="min-w-full divide-y divide-slate-200 bg-white">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Product</th>
                  <th className="th hidden sm:table-cell">Category</th>
                  <th className="th text-right">On shelf</th>
                  <th className="th hidden text-right md:table-cell">Cost each</th>
                  <th className="th hidden text-right md:table-cell">Value</th>
                  <th className="th text-right">History</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.product_id} className="hover:bg-slate-50">
                    <td className="td">
                      <span className="font-medium text-slate-900">{row.name}</span>
                      <span className="block font-mono text-xs text-slate-400">{row.sku}</span>
                    </td>
                    <td className="td hidden text-slate-500 sm:table-cell">
                      {row.category || '—'}
                    </td>
                    <td className="td text-right">
                      <StockBadge value={row.current_stock} />
                    </td>
                    <td className="td hidden text-right md:table-cell">{money(row.unit_cost)}</td>
                    <td className="td hidden text-right font-medium md:table-cell">
                      {money(row.stock_value_at_cost)}
                    </td>
                    <td className="td text-right">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          className="btn-ghost !px-2 !py-1.5"
                          onClick={() => setAdjustFor(row)}
                          aria-label={`Correct count for ${row.name}`}
                          title="Correct the count"
                        >
                          <SlidersHorizontal className="h-4 w-4" aria-hidden />
                        </button>
                        <button
                          type="button"
                          className="btn-ghost !px-2 !py-1.5"
                          onClick={() => setHistoryFor(row)}
                          aria-label={`View history for ${row.name}`}
                          title="View history"
                        >
                          <History className="h-4 w-4" aria-hidden />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Section>

      <MovementHistory product={historyFor} onClose={() => setHistoryFor(null)} />
      <AdjustModal product={adjustFor} onClose={() => setAdjustFor(null)} />
    </>
  )
}
