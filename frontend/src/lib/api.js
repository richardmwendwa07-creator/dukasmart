/**
 * Thin fetch wrapper around the DukaSmart API.
 *
 * Every backend error carries a plain-language `detail` string, so we surface
 * that directly to the operator rather than inventing our own wording.
 */

const TOKEN_KEY = 'dukasmart.token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private browsing — the session simply won't persist across reloads */
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(path, {
      method,
      headers,
      signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('Cannot reach the server. Check that the backend is running.', 0)
  }

  if (response.status === 204) return null

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    if (response.status === 401) setToken(null)
    const detail =
      (payload && (typeof payload.detail === 'string' ? payload.detail : null)) ||
      `Something went wrong (error ${response.status}).`
    throw new ApiError(detail, response.status)
  }

  return payload
}

const qs = (params) => {
  const search = new URLSearchParams()
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const string = search.toString()
  return string ? `?${string}` : ''
}

export const api = {
  // -- auth ---------------------------------------------------------------
  login: (email, password) =>
    request('/api/auth/login', { method: 'POST', body: { email, password } }),
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  me: () => request('/api/auth/me'),

  // -- catalog ------------------------------------------------------------
  products: (params) => request(`/api/products${qs(params)}`),
  createProduct: (body) => request('/api/products', { method: 'POST', body }),
  updateProduct: (id, body) => request(`/api/products/${id}`, { method: 'PUT', body }),
  deleteProduct: (id) => request(`/api/products/${id}`, { method: 'DELETE' }),

  suppliers: () => request('/api/suppliers'),
  createSupplier: (body) => request('/api/suppliers', { method: 'POST', body }),
  updateSupplier: (id, body) => request(`/api/suppliers/${id}`, { method: 'PUT', body }),
  deleteSupplier: (id) => request(`/api/suppliers/${id}`, { method: 'DELETE' }),

  // -- transactions -------------------------------------------------------
  sales: (params) => request(`/api/sales${qs(params)}`),
  createSale: (body) => request('/api/sales', { method: 'POST', body }),
  purchases: (params) => request(`/api/purchases${qs(params)}`),
  createPurchase: (body) => request('/api/purchases', { method: 'POST', body }),

  // -- inventory ----------------------------------------------------------
  stock: (params) => request(`/api/inventory/stock${qs(params)}`),
  movements: (params) => request(`/api/inventory/movements${qs(params)}`),
  createAdjustment: (body) => request('/api/inventory/adjustments', { method: 'POST', body }),

  // -- forecasting --------------------------------------------------------
  forecastConfig: () => request('/api/forecasts/config'),
  runForecasts: (body) => request('/api/forecasts/run', { method: 'POST', body }),
  latestForecasts: (params) => request(`/api/forecasts/latest${qs(params)}`),
  stockRisk: (params) => request(`/api/forecasts/risk${qs(params)}`),
  productForecast: (id, params) => request(`/api/forecasts/product/${id}${qs(params)}`),

  // -- planning -----------------------------------------------------------
  budgets: () => request('/api/budgets'),
  createBudget: (body) => request('/api/budgets', { method: 'POST', body }),
  runRecommendations: (body) => request('/api/recommendations/run', { method: 'POST', body }),
  recommendationRuns: (params) => request(`/api/recommendations/runs${qs(params)}`),
  latestRun: () => request('/api/recommendations/runs/latest'),
  run: (id) => request(`/api/recommendations/runs/${id}`),
  decide: (id, body) => request(`/api/recommendations/${id}`, { method: 'PATCH', body }),

  // -- reports ------------------------------------------------------------
  summary: (params) => request(`/api/summary${qs(params)}`),
  salesReport: (params) => request(`/api/reports/sales${qs(params)}`),
  purchasesReport: (params) => request(`/api/reports/purchases${qs(params)}`),
  forecastAccuracy: () => request('/api/reports/forecast-accuracy'),
  followThrough: () => request('/api/reports/recommendation-follow-through'),
}

// --------------------------------------------------------------------------
// Formatting helpers (Kenyan shillings, whole units)
// --------------------------------------------------------------------------
export const money = (value) =>
  `KES ${Number(value || 0).toLocaleString('en-KE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`

export const moneyExact = (value) =>
  `KES ${Number(value || 0).toLocaleString('en-KE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`

export const units = (value) => Math.round(Number(value || 0)).toLocaleString('en-KE')

export const shortDate = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString('en-KE', { day: 'numeric', month: 'short' })
}

export const longDate = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })
}

export const dateTime = (value) => {
  if (!value) return ''
  // The API sends naive UTC timestamps; mark them so the browser localises correctly.
  const iso = /(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('en-KE', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const todayISO = () => new Date().toISOString().slice(0, 10)
