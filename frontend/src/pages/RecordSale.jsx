import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, ShoppingCart, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { EmptyState, ErrorNote, Field, PageHeader, Section, Spinner } from '../components/ui'
import { api, money, moneyExact, todayISO, units } from '../lib/api'

const emptyLine = () => ({ key: crypto.randomUUID(), product_id: '', quantity: '1' })

export default function RecordSale() {
  const queryClient = useQueryClient()
  const [lines, setLines] = useState([emptyLine()])
  const [saleDate, setSaleDate] = useState(todayISO())
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)

  const { data: products, isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => api.products(),
  })

  const byId = useMemo(
    () => Object.fromEntries((products || []).map((p) => [String(p.id), p])),
    [products],
  )

  const chosen = new Set(lines.map((l) => l.product_id).filter(Boolean))

  const total = lines.reduce((sum, line) => {
    const product = byId[line.product_id]
    const qty = Number(line.quantity)
    if (!product || !Number.isFinite(qty) || qty <= 0) return sum
    return sum + product.selling_price * qty
  }, 0)

  const mutation = useMutation({
    mutationFn: (body) => api.createSale(body),
    onSuccess: (sale) => {
      toast.success(`Sale recorded — ${money(sale.total_amount)}`)
      setLines([emptyLine()])
      setNote('')
      setError(null)
      queryClient.invalidateQueries()
    },
    onError: (err) => setError(err),
  })

  const setLine = (key, patch) =>
    setLines((current) => current.map((l) => (l.key === key ? { ...l, ...patch } : l)))

  function onSubmit(event) {
    event.preventDefault()
    setError(null)

    const items = []
    for (const line of lines) {
      if (!line.product_id) continue
      const quantity = Number(line.quantity)
      if (!Number.isInteger(quantity) || quantity <= 0) {
        setError(new Error('Every quantity must be a whole number above zero.'))
        return
      }
      const product = byId[line.product_id]
      if (quantity > product.current_stock) {
        setError(
          new Error(
            `Not enough ${product.name} in stock: you have ${product.current_stock} but entered ${quantity}.`,
          ),
        )
        return
      }
      items.push({ product_id: Number(line.product_id), quantity })
    }

    if (items.length === 0) {
      setError(new Error('Add at least one product to the sale.'))
      return
    }
    mutation.mutate({ date: saleDate, note: note.trim() || null, items })
  }

  if (isLoading) return <Spinner label="Loading products…" />

  if ((products || []).length === 0) {
    return (
      <>
        <PageHeader title="Record a sale" />
        <Section>
          <EmptyState
            title="No products yet"
            description="Add products first, then you can record sales against them."
          />
        </Section>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Record a sale"
        subtitle="Add what the customer bought. Stock goes down as soon as you save."
      />

      <form onSubmit={onSubmit} className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Section title="What was sold">
            <div className="space-y-3">
              {lines.map((line, index) => {
                const product = byId[line.product_id]
                const qty = Number(line.quantity)
                const overStock = product && qty > product.current_stock
                return (
                  <div
                    key={line.key}
                    className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200"
                  >
                    <div className="flex items-start gap-2">
                      <div className="grid flex-1 gap-3 sm:grid-cols-[1fr_7rem]">
                        <div>
                          <label className="label sr-only">Product {index + 1}</label>
                          <select
                            className="input"
                            value={line.product_id}
                            onChange={(e) => setLine(line.key, { product_id: e.target.value })}
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
                        </div>
                        <div>
                          <label className="label sr-only">Quantity</label>
                          <input
                            className="input"
                            type="number"
                            min="1"
                            step="1"
                            inputMode="numeric"
                            value={line.quantity}
                            onChange={(e) => setLine(line.key, { quantity: e.target.value })}
                            placeholder="Qty"
                          />
                        </div>
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

                    {product && (
                      <p
                        className={`mt-2 text-xs ${overStock ? 'font-semibold text-rose-600' : 'text-slate-500'}`}
                      >
                        {overStock
                          ? `Only ${units(product.current_stock)} in stock.`
                          : `${money(product.selling_price)} each · line total ${money(
                              product.selling_price * (Number.isFinite(qty) && qty > 0 ? qty : 0),
                            )}`}
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
          <Section title="Sale details">
            <div className="space-y-4">
              <Field label="Date">
                <input
                  className="input"
                  type="date"
                  value={saleDate}
                  max={todayISO()}
                  onChange={(e) => setSaleDate(e.target.value)}
                />
              </Field>
              <Field label="Note" hint="Optional — e.g. a customer name.">
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
              <span className="text-sm font-medium text-slate-600">Total</span>
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
                <ShoppingCart className="h-5 w-5" aria-hidden />
              )}
              Save sale
            </button>
            <p className="mt-3 text-center text-xs text-slate-500">
              Stock and history update together — if anything is wrong, nothing is saved.
            </p>
          </Section>
        </div>
      </form>
    </>
  )
}
