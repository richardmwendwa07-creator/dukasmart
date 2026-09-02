import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  BarChart3,
  Boxes,
  ClipboardList,
  Home,
  LogOut,
  Menu,
  Package,
  ShoppingCart,
  Store,
  Truck,
  TrendingUp,
  Wallet,
  X,
} from 'lucide-react'
import { useAuth } from '../lib/auth'

/**
 * Navigation is written in shop language, not system language:
 * "Products running low" rather than "stockout risk classification".
 */
const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true, primary: true },
  { to: '/sell', label: 'Record a sale', icon: ShoppingCart, primary: true },
  { to: '/receive', label: 'Record delivery', icon: Truck, primary: true },
  { to: '/stock', label: 'Stock', icon: Boxes, primary: true },
  { to: '/restock', label: 'What to buy', icon: Wallet, ownerOnly: true, primary: true },
  { to: '/forecasts', label: 'Sales outlook', icon: TrendingUp },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/suppliers', label: 'Suppliers', icon: Store },
  { to: '/history', label: 'Sales & deliveries', icon: ClipboardList },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
]

function Brand({ compact = false }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-700 text-white">
        <Store className="h-5 w-5" aria-hidden />
      </span>
      {!compact && (
        <div className="leading-tight">
          <p className="font-bold tracking-tight text-slate-900">DukaSmart</p>
          <p className="text-[11px] text-slate-500">Stock &amp; restock helper</p>
        </div>
      )}
    </div>
  )
}

function NavItems({ items, onNavigate }) {
  return (
    <nav className="space-y-1">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-brand-50 text-brand-800 ring-1 ring-brand-200'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`
          }
        >
          <Icon className="h-5 w-5 shrink-0" aria-hidden />
          <span className="truncate">{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

export default function Layout() {
  const { user, logout, isOwner } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  const items = NAV.filter((item) => !item.ownerOnly || isOwner)
  // The phone bottom bar shows only the five things done most often.
  const bottomItems = items.filter((item) => item.primary).slice(0, 5)
  const currentLabel =
    items.find((item) => (item.end ? location.pathname === item.to : location.pathname.startsWith(item.to)))
      ?.label ?? 'DukaSmart'

  return (
    <div className="min-h-dvh lg:flex">
      {/* ---------------- Desktop sidebar ---------------- */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 lg:flex">
        <div className="px-2 py-2">
          <Brand />
        </div>
        <div className="mt-6 flex-1 overflow-y-auto">
          <NavItems items={items} />
        </div>
        <div className="mt-4 border-t border-slate-200 pt-4">
          <div className="px-3 pb-3">
            <p className="truncate text-sm font-semibold text-slate-800">{user?.name}</p>
            <p className="text-xs capitalize text-slate-500">
              {user?.role === 'owner' ? 'Shop owner' : 'Shop assistant'}
            </p>
          </div>
          <button type="button" onClick={logout} className="btn-ghost w-full !justify-start">
            <LogOut className="h-4 w-4" aria-hidden />
            Sign out
          </button>
        </div>
      </aside>

      {/* ---------------- Mobile drawer ---------------- */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative flex h-full w-72 max-w-[85%] flex-col bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between">
              <Brand />
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="btn-ghost !px-2"
              >
                <X className="h-5 w-5" aria-hidden />
                <span className="sr-only">Close menu</span>
              </button>
            </div>
            <div className="mt-6 flex-1 overflow-y-auto">
              <NavItems items={items} onNavigate={() => setDrawerOpen(false)} />
            </div>
            <div className="border-t border-slate-200 pt-4">
              <div className="px-3 pb-3">
                <p className="truncate text-sm font-semibold text-slate-800">{user?.name}</p>
                <p className="text-xs text-slate-500">
                  {user?.role === 'owner' ? 'Shop owner' : 'Shop assistant'}
                </p>
              </div>
              <button type="button" onClick={logout} className="btn-ghost w-full !justify-start">
                <LogOut className="h-4 w-4" aria-hidden />
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- Main column ---------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="btn-ghost !px-2"
            aria-label="Open menu"
          >
            <Menu className="h-6 w-6" aria-hidden />
          </button>
          <span className="truncate font-semibold text-slate-900">{currentLabel}</span>
          <span className="ml-auto">
            <Brand compact />
          </span>
        </header>

        <main className="flex-1 px-4 py-6 pb-28 sm:px-6 lg:px-8 lg:pb-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>

        {/* ---------------- Mobile bottom bar ---------------- */}
        <nav className="pb-safe fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-slate-200 bg-white/95 pt-1 backdrop-blur lg:hidden">
          {bottomItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-1 py-1.5 text-[10px] font-medium ${
                  isActive ? 'text-brand-700' : 'text-slate-500'
                }`
              }
            >
              <Icon className="h-5 w-5" aria-hidden />
              <span className="w-full truncate text-center leading-tight">
                {label.replace('Record a ', '').replace('Record ', '')}
              </span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}
