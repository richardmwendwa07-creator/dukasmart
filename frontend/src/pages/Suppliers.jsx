import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Pencil, Phone, Plus, Store, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  EmptyState,
  ErrorNote,
  Field,
  Modal,
  PageHeader,
  Section,
  Spinner,
} from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

function SupplierForm({ open, supplier, onClose }) {
  const queryClient = useQueryClient()
  const editing = Boolean(supplier)
  const [form, setForm] = useState({ name: '', contact: '', notes: '' })
  const [error, setError] = useState(null)
  const [seeded, setSeeded] = useState(null)

  if (open && seeded !== (supplier?.id ?? 'new')) {
    setSeeded(supplier?.id ?? 'new')
    setForm({
      name: supplier?.name || '',
      contact: supplier?.contact || '',
      notes: supplier?.notes || '',
    })
    setError(null)
  }

  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const mutation = useMutation({
    mutationFn: (body) =>
      editing ? api.updateSupplier(supplier.id, body) : api.createSupplier(body),
    onSuccess: () => {
      toast.success(editing ? 'Supplier updated.' : 'Supplier added.')
      queryClient.invalidateQueries()
      setSeeded(null)
      onClose()
    },
    onError: (err) => setError(err),
  })

  function onSubmit(event) {
    event.preventDefault()
    setError(null)
    if (!form.name.trim()) return setError(new Error('Give the supplier a name.'))
    mutation.mutate({
      name: form.name.trim(),
      contact: form.contact.trim() || null,
      notes: form.notes.trim() || null,
    })
  }

  const close = () => {
    setSeeded(null)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={editing ? 'Edit supplier' : 'Add a supplier'}
      description="Who you buy stock from."
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Name" required>
          <input className="input" value={form.name} onChange={set('name')} />
        </Field>
        <Field label="Phone or contact">
          <input
            className="input"
            value={form.contact}
            onChange={set('contact')}
            placeholder="e.g. 0722 000 000"
          />
        </Field>
        <Field label="Notes" hint="Delivery days, payment terms, anything useful.">
          <textarea className="input" rows={3} value={form.notes} onChange={set('notes')} />
        </Field>

        <ErrorNote error={error} />

        <div className="flex gap-2">
          <button type="button" className="btn-secondary flex-1" onClick={close}>
            Cancel
          </button>
          <button type="submit" className="btn-primary flex-1" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
            {editing ? 'Save changes' : 'Add supplier'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function Suppliers() {
  const { isOwner } = useAuth()
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => api.suppliers(),
  })

  const remove = useMutation({
    mutationFn: (id) => api.deleteSupplier(id),
    onSuccess: () => {
      toast.success('Supplier deleted.')
      queryClient.invalidateQueries()
    },
    onError: (err) => toast.error(err.message),
  })

  if (isLoading) return <Spinner label="Loading suppliers…" />
  if (error) return <ErrorNote error={error} />

  return (
    <>
      <PageHeader title="Suppliers" subtitle="The wholesalers and distributors you buy from.">
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
            Add supplier
          </button>
        )}
      </PageHeader>

      {(data || []).length === 0 ? (
        <Section>
          <EmptyState
            icon={Store}
            title="No suppliers yet"
            description="Add the wholesalers you buy from so deliveries can be recorded against them."
          />
        </Section>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((supplier) => (
            <div key={supplier.id} className="card flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-100 text-brand-700">
                    <Store className="h-5 w-5" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-slate-900">{supplier.name}</p>
                    {supplier.contact && (
                      <a
                        href={`tel:${supplier.contact.replace(/\s/g, '')}`}
                        className="mt-0.5 flex items-center gap-1.5 text-sm text-brand-700 hover:underline"
                      >
                        <Phone className="h-3.5 w-3.5" aria-hidden />
                        {supplier.contact}
                      </a>
                    )}
                  </div>
                </div>
                {isOwner && (
                  <div className="flex shrink-0 gap-1">
                    <button
                      type="button"
                      className="btn-ghost !px-2 !py-1.5"
                      onClick={() => {
                        setEditing(supplier)
                        setFormOpen(true)
                      }}
                      aria-label={`Edit ${supplier.name}`}
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </button>
                    <button
                      type="button"
                      className="btn-ghost !px-2 !py-1.5 text-slate-400 hover:text-rose-600"
                      onClick={() => {
                        if (window.confirm(`Delete "${supplier.name}"?`)) remove.mutate(supplier.id)
                      }}
                      aria-label={`Delete ${supplier.name}`}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                )}
              </div>
              {supplier.notes && (
                <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600">
                  {supplier.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <SupplierForm
        open={formOpen}
        supplier={editing}
        onClose={() => {
          setFormOpen(false)
          setEditing(null)
        }}
      />
    </>
  )
}
