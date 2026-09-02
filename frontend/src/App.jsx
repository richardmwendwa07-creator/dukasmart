import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { useAuth } from './lib/auth'

import Dashboard from './pages/Dashboard'
import Forecasts from './pages/Forecasts'
import History from './pages/History'
import Login from './pages/Login'
import Products from './pages/Products'
import RecordPurchase from './pages/RecordPurchase'
import RecordSale from './pages/RecordSale'
import Reports from './pages/Reports'
import Restock from './pages/Restock'
import Stock from './pages/Stock'
import Suppliers from './pages/Suppliers'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner label="Signing you in…" className="min-h-dvh" />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RequireOwner({ children }) {
  const { isOwner } = useAuth()
  if (!isOwner) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="sell" element={<RecordSale />} />
        <Route path="receive" element={<RecordPurchase />} />
        <Route path="stock" element={<Stock />} />
        <Route path="forecasts" element={<Forecasts />} />
        <Route path="products" element={<Products />} />
        <Route path="suppliers" element={<Suppliers />} />
        <Route path="history" element={<History />} />
        <Route path="reports" element={<Reports />} />
        <Route
          path="restock"
          element={
            <RequireOwner>
              <Restock />
            </RequireOwner>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
