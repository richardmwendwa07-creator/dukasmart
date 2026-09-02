import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Trash2, Truck } from 'lucide-react'
import { toast } from 'sonner'
import { EmptyState, ErrorNote, Field, PageHeader, Section, Spinner } from '../components/ui'
import { api, money, moneyExact, todayISO, units } from '../lib/api'

const emptyLine = () => ({ key: crypto.randomUUID(), product_id: '', quantity: '', unit_cost: '' })

export default function RecordPurchase() {
  const queryClient = useQueryClient()
  const [lines, setLines] = useState([emptyLine()])
  const [supplierId, setSupplierId] = useState('')
  const [dateReceived, setDateReceived] = useState(todayISO())
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)

  const { data: products, isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => api.products(),
  })
  const { data: suppliers } = useQuery({ queryKey: ['suppliers'], queryFn: () => api.suppliers() })

  const byId = useMemo(
    () => Object.fromEntries((products || []).map((p) => [String(p.id), p])),
    [products],
  )
  const chosen = new Set(lines.map((l) => l.product_id).filter(Boolean))

  const total = lines.reduce((sum, line) => {
    const qty = Number(line.quantity)
    const cost = Number(line.unit_cost)
    if (!Number.isFinite(qty) || !Number.isFinite(cost) || qty <= 0 || cost < 0) return sum
    return sum + qty * cost
  }, 0)

  const mutation = useMutation({
    mutationFn: (body) => api.createPurchase(body),
    onSuccess: (purchase) => {
      toast.success(`Delivery recorded — ${money(purchase.total_cost)}`)
      setLines([emptyLine()])
      setNote('')
      setError(null)
      queryClient.invalidateQueries()
    },
    onError: (err) => setError(err),
  })

  const setLine = (key, patch) =>
    setLines((current) => current.map((l) => (l.key === key ? { ...l, ...patch } : l)))

  // Pre-fill the cost with what this product usually costs, so the operator
  // only has to change it when the supplier's price actually moved.
  function onPickProduct(key, productId) {
    const product = byId[productId]
    setLine(key, {
      product_id: productId,
      unit_cost: product && product.default_unit_cost > 0 ? String(product.default_unit_cost) : '',
    })
  }

  function onSubmit(event) {
    event.preventDefault()
    setError(null)

    if (!supplierId) {
      setError(new Error('Choose which supplier this delivery came from.'))
      return
    }

    const items = []
    for (const line of lines) {
      if (!line.product_id) continue
      const quantity = Number(line.quantity)
      const unitCost = Number(line.unit_cost)
      if (!Number.isInteger(quantity) || quantity <= 0) {
        setError(new Error('Every quantity must be a whole number above zero.'))
        return
      }
      if (!Number.isFinite(unitCost) || unitCost < 0) {
        setError(new Error('Every unit cost must be zero or more.'))
        return
      }
      items.push({
        product_id: Number(line.product_id),
        quantity_received: quantity,
        unit_cost: unitCost,
      })
    }

    if (items.length === 0) {
      setError(new Error('Add at least one product to the delivery.'))
      return
    }
    mutation.mutate({
      supplier_id: Number(supplierId),
      date_received: dateReceived,
      note: note.trim() || null,
      items,
    })
  }

  if (isLoading) return <Spinner label="Loading products…" />

  if ((suppliers || []).length === 0) {
    return (
      <>
        <PageHeader title="Record a delivery" />
        <Section>
          <EmptyState
            title="No suppliers yet"
            description="Add a supplier first, then you can record deliveries from them."
          />
        </Section>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Record a delivery"
        subtitle="Enter stock that arrived from a supplier. Shelf counts go up as soon as you save."
      />

      <form onSubmit={onSubmit} className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Section title="What arrived">
            <div className="space-y-3">
              {lines.map((line) => {
                const product = byId[line.product_id]
                const qty = Number(line.quantity)
                const cost = Number(line.unit_cost)
                const lineTotal =
                  Number.isFinite(qty) && Number.isFinite(cost) && qty > 0 && cost >= 0
                    ? qty * cost
                    : 0
                return (
                  <div key={line.key} className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
                    <div className="flex items-start gap-2">
                      <div className="grid flex-1 gap-3 sm:grid-cols-[1fr_6rem_7rem]">
                        <select
                          className="input"
                          value={line.product_id}
                          onChange={(e) => onPickProduct(line.key, e.target.value)}
                          aria-label="Product"
                        >
                          <option value="">Choose a product…</option>
                          {(products || []).map((p) => (
                            <option
                              key={p.id}
                              value={p.id}
                              disabled={chosen.has(String(p.id)) && String(p.id) !== line.product_id}
                            >
                              {p.name} — {units(p.current_stock)} left
                            </option>
                          ))}
                        </select>
                        <input
                          className="input"
                          type="number"
                          min="1"
                          step="1"
                          inputMode="numeric"
                          placeholder="Qty"
                          aria-label="Quantity received"
                          value={line.quantity}
                          onChange={(e) => setLine(line.key, { quantity: e.target.value })}
                        />
                        <input
                          className="input"
                          type="number"
                          min="0"
                          step="0.01"
                          inputMode="decimal"
                          placeholder="Cost each"
                          aria-label="Unit cost"
                          value={line.unit_cost}
                          onChange={(e) => setLine(line.key, { unit_cost: e.target.value })}
                        />
                      </div>
                      <button
                        type="button"
                        className="btn-ghost mt-0.5 !px-2 text-slate-400 hover:text-rose-600"
                        onClick={() =>
                          setLines((current) =>
                            current.length === 1
                              ? [emptyLine()]
                              : current.filter((l) => l.key !== line.key),
                          )
                        }
                        aria-label="Remove line"
                      >
                        <Trash2 className="h-5 w-5" aria-hidden />
                      </button>
                    </div>
                    {product && lineTotal > 0 && (
                      <p className="mt-2 text-xs text-slate-500">
                        Line total {money(lineTotal)} · new shelf count will be{' '}
                        {units(product.current_stock + qty)}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>

            <button
              type="button"
              className="btn-secondary mt-3 w-full"
              onClick={() => setLines((current) => [...current, emptyLine()])}
            >
              <Plus className="h-4 w-4" aria-hidden />
              Add another product
            </button>
          </Section>
        </div>

        <div className="space-y-5">
          <Section title="Delivery details">
            <div className="space-y-4">
              <Field label="Supplier" required>
                <select
                  className="input"
                  value={supplierId}
                  onChange={(e) => setSupplierId(e.target.value)}
                >
                  <option value="">Choose a supplier…</option>
                  {(suppliers || []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Date received">
                <input
                  className="input"
                  type="date"
                  value={dateReceived}
                  max={todayISO()}
                  onChange={(e) => setDateReceived(e.target.value)}
                />
              </Field>
              <Field label="Note" hint="Optional — e.g. an invoice number.">
                <input
                  className="input"
                  value={note}
                  maxLength={255}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Optional"
                />
              </Field>
            </div>
          </Section>

          <Section>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium text-slate-600">Total cost</span>
              <span className="text-3xl font-bold tracking-tight text-slate-900">
                {moneyExact(total)}
              </span>
            </div>

            <ErrorNote error={error} className="mt-4" />

            <button
              type="submit"
              className="btn-primary mt-4 w-full !py-3 !text-base"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? (
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
              ) : (
                <Truck className="h-5 w-5" aria-hidden />
              )}
              Save delivery
            </button>
          </Section>
        </div>
      </form>
    </>
  )
}
