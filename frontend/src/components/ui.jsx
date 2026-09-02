import { AlertCircle, Inbox, Loader2, X } from 'lucide-react'
import { useEffect } from 'react'

// --------------------------------------------------------------------------
// Page scaffolding
// --------------------------------------------------------------------------
export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-600">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}

export function Section({ title, description, action, children, className = '' }) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
            {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

// --------------------------------------------------------------------------
// State placeholders
// --------------------------------------------------------------------------
export function Spinner({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-10 text-slate-500 ${className}`}>
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorNote({ error, className = '' }) {
  if (!error) return null
  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-xl bg-rose-50 p-4 text-sm text-rose-800 ring-1 ring-rose-200 ${className}`}
    >
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <span>{error.message || String(error)}</span>
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, description, children }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 px-6 py-12 text-center">
      <Icon className="h-9 w-9 text-slate-300" aria-hidden />
      <p className="mt-3 font-semibold text-slate-700">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}

// --------------------------------------------------------------------------
// Stat tile
// --------------------------------------------------------------------------
export function Stat({ label, value, sublabel, icon: Icon, tone = 'default' }) {
  const tones = {
    default: 'bg-slate-100 text-slate-600',
    brand: 'bg-brand-100 text-brand-700',
    danger: 'bg-rose-100 text-rose-700',
    warn: 'bg-amber-100 text-amber-700',
    ok: 'bg-emerald-100 text-emerald-700',
  }
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-1.5 text-2xl font-bold tracking-tight text-slate-900">{value}</p>
          {sublabel && <p className="mt-1 text-xs text-slate-500">{sublabel}</p>}
        </div>
        {Icon && (
          <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tones[tone]}`}>
            <Icon className="h-5 w-5" aria-hidden />
          </span>
        )}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// Modal
// --------------------------------------------------------------------------
export function Modal({ open, onClose, title, description, children, wide = false }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => event.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`relative max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl ${
          wide ? 'sm:max-w-3xl' : 'sm:max-w-lg'
        }`}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
          </div>
          <button type="button" onClick={onClose} className="btn-ghost -mr-2 -mt-2 !px-2">
            <X className="h-5 w-5" aria-hidden />
            <span className="sr-only">Close</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// Form field
// --------------------------------------------------------------------------
export function Field({ label, hint, error, children, required }) {
  return (
    <div>
      <label className="label">
        {label}
        {required && <span className="ml-0.5 text-rose-600">*</span>}
      </label>
      {children}
      {hint && !error && <p className="hint">{hint}</p>}
      {error && <p className="mt-1 text-xs font-medium text-rose-600">{error}</p>}
    </div>
  )
}

// --------------------------------------------------------------------------
// Responsive table wrapper
// --------------------------------------------------------------------------
export function TableWrap({ children }) {
  return (
    <div className="scroll-x -mx-5 rounded-xl px-5 sm:mx-0 sm:px-0">
      <div className="min-w-full overflow-hidden rounded-xl ring-1 ring-slate-200">{children}</div>
    </div>
  )
}

// --------------------------------------------------------------------------
// A labelled progress bar, used for budget usage and score breakdowns
// --------------------------------------------------------------------------
export function Meter({ value, max = 1, tone = 'brand', label }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  const tones = {
    brand: 'bg-brand-600',
    danger: 'bg-rose-500',
    warn: 'bg-amber-500',
    ok: 'bg-emerald-500',
    slate: 'bg-slate-400',
  }
  return (
    <div>
      {label && (
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>{label}</span>
          <span className="font-medium text-slate-700">{Math.round(pct)}%</span>
        </div>
      )}
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`h-full rounded-full ${tones[tone]}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
