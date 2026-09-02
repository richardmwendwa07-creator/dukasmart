import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Loader2, Store } from 'lucide-react'
import { toast } from 'sonner'
import { ErrorNote, Field, Spinner } from '../components/ui'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'

export default function Login() {
  const { user, loading, login } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'staff' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (loading) return <Spinner label="Loading…" className="min-h-dvh" />
  if (user) return <Navigate to="/" replace />

  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  async function onSubmit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(form.email.trim(), form.password)
      } else {
        const result = await api.register({
          name: form.name.trim(),
          email: form.email.trim(),
          password: form.password,
          role: form.role,
        })
        // Registering signs you straight in.
        await login(form.email.trim(), form.password)
        toast.success(`Welcome, ${result.user.name}.`)
      }
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  function useDemo(email) {
    setMode('login')
    setForm({ name: '', email, password: 'duka1234', role: 'staff' })
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* ---- Brand panel (desktop only) ---- */}
      <div className="hidden flex-col justify-between bg-brand-800 p-10 text-white lg:flex">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-white/15">
            <Store className="h-6 w-6" aria-hidden />
          </span>
          <div>
            <p className="text-xl font-bold tracking-tight">DukaSmart</p>
            <p className="text-sm text-brand-200">Stock &amp; restock helper</p>
          </div>
        </div>

        <div className="max-w-md">
          <h1 className="text-3xl font-bold leading-tight">
            Know what to buy first, when the money is tight.
          </h1>
          <p className="mt-4 text-brand-100">
            DukaSmart watches what you sell, works out what you are likely to sell next, and
            tells you which products to restock first with the money you actually have.
          </p>
          <ul className="mt-8 space-y-3 text-sm text-brand-100">
            {[
              'Always-current stock count, worked out from every sale and delivery.',
              'Sales outlook only where there is enough history to be honest about it.',
              'A restock plan you can accept, change, or reject — it never orders for you.',
            ].map((line) => (
              <li key={line} className="flex gap-3">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-300" />
                {line}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-brand-300">
          Decision support only. DukaSmart never places orders or moves money.
        </p>
      </div>

      {/* ---- Form panel ---- */}
      <div className="flex items-center justify-center bg-slate-100 px-4 py-10">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-700 text-white">
              <Store className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-lg font-bold tracking-tight text-slate-900">DukaSmart</p>
              <p className="text-xs text-slate-500">Stock &amp; restock helper</p>
            </div>
          </div>

          <div className="card p-6">
            <h2 className="text-xl font-bold text-slate-900">
              {mode === 'login' ? 'Sign in' : 'Create an account'}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {mode === 'login'
                ? 'Enter the email and password for your shop.'
                : 'The first account created becomes the shop owner.'}
            </p>

            <form onSubmit={onSubmit} className="mt-5 space-y-4">
              {mode === 'register' && (
                <Field label="Your name" required>
                  <input
                    className="input"
                    value={form.name}
                    onChange={set('name')}
                    autoComplete="name"
                    required
                  />
                </Field>
              )}

              <Field label="Email" required>
                <input
                  className="input"
                  type="email"
                  value={form.email}
                  onChange={set('email')}
                  autoComplete="email"
                  required
                />
              </Field>

              <Field
                label="Password"
                required
                hint={mode === 'register' ? 'At least 8 characters.' : undefined}
              >
                <input
                  className="input"
                  type="password"
                  value={form.password}
                  onChange={set('password')}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  required
                />
              </Field>

              {mode === 'register' && (
                <Field label="Role" hint="Assistants record sales and deliveries. Owners also plan restocking.">
                  <select className="input" value={form.role} onChange={set('role')}>
                    <option value="staff">Shop assistant</option>
                    <option value="owner">Shop owner</option>
                  </select>
                </Field>
              )}

              <ErrorNote error={error} />

              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </button>
            </form>

            <button
              type="button"
              className="mt-4 w-full text-sm font-medium text-brand-700 hover:underline"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError(null)
              }}
            >
              {mode === 'login'
                ? 'No account yet? Create one'
                : 'Already have an account? Sign in'}
            </button>
          </div>

          {/* Demo credentials from the seed script. */}
          <div className="card mt-4 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Demo accounts
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => useDemo('owner@dukasmart.co.ke')}
                className="btn-secondary !justify-start text-left"
              >
                <span>
                  <span className="block font-semibold">Owner</span>
                  <span className="block text-[11px] font-normal text-slate-500">
                    Full access
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={() => useDemo('staff@dukasmart.co.ke')}
                className="btn-secondary !justify-start text-left"
              >
                <span>
                  <span className="block font-semibold">Assistant</span>
                  <span className="block text-[11px] font-normal text-slate-500">
                    Sales &amp; deliveries
                  </span>
                </span>
              </button>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Both use the password <code className="font-mono">duka1234</code>. Run the seed
              script first: <code className="font-mono">python backend/seed.py --reset</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
