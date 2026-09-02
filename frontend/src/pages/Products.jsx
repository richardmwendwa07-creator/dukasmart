import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Package, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  EmptyState,
  ErrorNote,
  Field,
  Modal,
  PageHeader,
  Section,
  Spinner,
  TableWrap,
} from '../components/ui'
import { api, money, units } from '../lib/api'
import { useAuth } from '../lib/auth'

const blank = {
  name: '',
  sku: '',
  category: '',
  selling_price: '',
  default_unit_cost: '',
  reorder_lead_time_days: '',
  preferred_supplier_id: '',
  opening_stock: '0',
}

function ProductForm({ open, product, suppliers, onClose }) {
  const queryClient = useQueryClient()
  const editing = Boolean(product)
  const [form, setForm] = useState(blank)
  const [error, setError] = useState(null)
  const [seeded, setSeeded] = useState(null)

  // Load the row into the form the first time this modal opens for it.
  if (open && seeded !== (product?.id ?? 'new')) {
    setSeeded(product?.id ?? 'new')
    setForm(
      product
        ? {
            name: product.name,
            sku: product.sku,
            category: product.category || '',
            selling_price: String(product.selling_price),
            default_unit_cost: String(product.default_unit_cost),
            reorder_lead_time_days:
              product.reorder_lead_time_days == null ? '' : String(product.reorder_lead_time_days),
            preferred_supplier_id:
              product.preferred_supplier_id == null ? '' : String(product.preferred_supplier_id),
            opening_stock: '0',
          }
        : blank,
    )
    setError(null)
  }

  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const mutation = useMutation({
    mutationFn: (body) =>
      editing ? api.updateProduct(product.id, body) : api.createProduct(body),
    onSuccess: () => {
      toast.success(editing ? 'Product updated.' : 'Product added.')
      queryClient.invalidateQueries()
      setSeeded(null)
      onClose()
    },
    onError: (err) => setError(err),
  })

  function onSubmit(event) {
    event.preventDefault()
    setError(null)

    const price = Number(form.selling_price)
    const cost = Number(form.default_unit_cost || 0)
    if (!form.name.trim()) return setError(new Error('Give the product a name.'))
    if (!editing && !form.sku.trim()) return setError(new Error('Give the product a short code.'))
    if (!Number.isFinite(price) || price <= 0)
      return setError(new Error('Selling price must be more than zero.'))
    if (!Number.isFinite(cost) || cost < 0)
      return setError(new Error('Purchase cost cannot be negative.'))

    const supplierId = form.preferred_supplier_id ? Number(form.preferred_supplier_id) : null
    const lead = form.reorder_lead_time_days === '' ? null : Number(form.reorder_lead_time_days)
    if (lead !== null && (!Number.isInteger(lead) || lead < 0))
      return setError(new Error('Delivery time must be a whole number of days.'))

    const body = {
      name: form.name.trim(),
      category: form.category.trim() || null,
      selling_price: price,
      default_unit_cost: cost,
      reorder_lead_time_days: lead,
      preferred_supplier_id: supplierId,
      supplier_ids: supplierId ? [supplierId] : [],
    }

    if (!editing) {
      const opening = Number(form.opening_stock || 0)
      if (!Number.isInteger(opening) || opening < 0)
        return setError(new Error('Opening stock must be zero or a whole number.'))
      body.sku = form.sku.trim()
      body.opening_stock = opening
    }

    mutation.mutate(body)
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        setSeeded(null)
        onClose()
      }}
      title={editing ? 'Edit product' : 'Add a product'}
      description={
        editing
          ? 'The shelf count is not edited here — it comes from sales and deliveries.'
          : 'Enter what you sell and what it usually costs you to buy.'
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name" required>
          <input className="input" value={form.name} onChange={set('name')} />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Short code"
            required={!editing}
            hint={editing ? 'Codes cannot be changed.' : 'e.g. MF2KG'}
          >
            <input
              className="input disabled:bg-slate-100"
              value={form.sku}
              onChange={set('sku')}
              disabled={editing}
            />
          </Field>
          <Field label="Category">
            <input
              className="input"
              value={form.category}
              onChange={set('category')}
              placeholder="e.g. Staples"
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Selling price (KES)" required>
            <input
              className="input"
              type="number"
              min="0.01"
              step="0.01"
              inputMode="decimal"
              value={form.selling_price}
              onChange={set('selling_price')}
            />
          </Field>
          <Field label="Usual cost to buy (KES)" hint="Used when planning a restock.">
            <input
              className="input"
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={form.default_unit_cost}
              onChange={set('default_unit_cost')}
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Main supplier">
            <select
              className="input"
              value={form.preferred_supplier_id}
              onChange={set('preferred_supplier_id')}
            >
              <option value="">Not set</option>
              {(suppliers || []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Days to deliver"
            hint="How long after ordering it usually arrives."
          >
            <input
              className="input"
              type="number"
              min="0"
              step="1"
              inputMode="numeric"
              value={form.reorder_lead_time_days}
              onChange={set('reorder_lead_time_days')}
              placeholder="Optional"
            />
          </Field>
        </div>

        {!editing && (
          <Field
            label="How many on the shelf now"
            hint="Recorded as an opening count so the history stays complete."
          >
            <input
              className="input"
              type="number"
              min="0"
              step="1"
              inputMode="numeric"
              value={form.opening_stock}
              onChange={set('opening_stock')}
            />
          </Field>
        )}

        <ErrorNote error={error} />

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            className="btn-secondary flex-1"
            onClick={() => {
              setSeeded(null)
              onClose()
            }}
          >
            Cancel
          </button>
          <button type="submit" className="btn-primary flex-1" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            {editing ? 'Save changes' : 'Add product'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function Products() {
  const { isOwner } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['products'],
    queryFn: () => api.products(),
  })
  const { data: suppliers } = useQuery({ queryKey: ['suppliers'], queryFn: () => api.suppliers() })

  const remove = useMutation({
    mutationFn: (id) => api.deleteProduct(id),
    onSuccess: () => {
      toast.success('Product removed from the active list.')
      queryClient.invalidateQueries()
    },
    onError: (err) => toast.error(err.message),
  })

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase()
    const list = data || []
    if (!term) return list
    return list.filter(
      (p) => p.name.toLowerCase().includes(term) || p.sku.toLowerCase().includes(term),
    )
  }, [data, search])

  if (isLoading) return <Spinner label="Loading products…" />
  if (error) return <ErrorNote error={error} />

  return (
    <>
      <PageHeader title="Products" subtitle="Everything the shop sells.">
        {isOwner && (
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setEditing(null)
              setFormOpen(true)
            }}
          >
            <Plus className="h-4 w-4" aria-hidden />
            Add product
          </button>
        )}
      </PageHeader>

      <Section>
        <div className="relative mb-4">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
            aria-hidden
          />
          <input
            className="input !pl-11"
            placeholder="Search products"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {rows.length === 0 ? (
          <EmptyState
            icon={Package}
            title={search ? 'Nothing matches that search' : 'No products yet'}
            description={search ? undefined : 'Add your first product to get started.'}
          />
        ) : (
          <TableWrap>
            <table className="min-w-full divide-y divide-slate-200 bg-white">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Product</th>
                  <th className="th hidden sm:table-cell">Supplier</th>
                  <th className="th text-right">Sells for</th>
                  <th className="th hidden text-right md:table-cell">Costs</th>
                  <th className="th text-right">On shelf</th>
                  {isOwner && <th className="th text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="td">
                      <span className="font-medium text-slate-900">{p.name}</span>
                      <span className="block font-mono text-xs text-slate-400">
                        {p.sku}
                        {p.category ? ` · ${p.category}` : ''}
                      </span>
                    </td>
                    <td className="td hidden text-slate-500 sm:table-cell">
                      {p.suppliers?.find((s) => s.id === p.preferred_supplier_id)?.name ||
                        p.suppliers?.[0]?.name ||
                        '—'}
                    </td>
                    <td className="td text-right font-medium">{money(p.selling_price)}</td>
                    <td className="td hidden text-right text-slate-500 md:table-cell">
                      {p.default_unit_cost > 0 ? money(p.default_unit_cost) : '—'}
                    </td>
                    <td className="td text-right">
                      <span
                        className={
                          p.current_stock <= 0
                            ? 'badge-danger'
                            : p.current_stock <= 5
                              ? 'badge-warn'
                              : 'badge-muted'
                        }
                      >
                        {units(p.current_stock)}
                      </span>
                    </td>
                    {isOwner && (
                      <td className="td text-right">
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            className="btn-ghost !px-2 !py-1.5"
                            onClick={() => {
                              setEditing(p)
                              setFormOpen(true)
                            }}
                            aria-label={`Edit ${p.name}`}
                          >
                            <Pencil className="h-4 w-4" aria-hidden />
                          </button>
                          <button
                            type="button"
                            className="btn-ghost !px-2 !py-1.5 text-slate-400 hover:text-rose-600"
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Remove "${p.name}" from the active product list?\n\nIts sales and delivery history is kept.`,
                                )
                              )
                                remove.mutate(p.id)
                            }}
                            aria-label={`Remove ${p.name}`}
                          >
                            <Trash2 className="h-4 w-4" aria-hidden />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Section>

      <ProductForm
        open={formOpen}
        product={editing}
        suppliers={suppliers}
        onClose={() => {
          setFormOpen(false)
          setEditing(null)
        }}
      />
    </>
  )
}
