/**
 * Mira API client — connects dashboard to the FastAPI backend.
 */

const API_BASE = '/api'

async function fetchAPI(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

// ── Status & KPIs ─────────────────────────────────────────────
export const getStatus = () => fetchAPI('/status')
export const getKPIs = () => fetchAPI('/kpis')

// ── Memory ────────────────────────────────────────────────────
export const getMemories = (params = {}) => {
  const query = new URLSearchParams(params).toString()
  return fetchAPI(`/memories?${query}`)
}
export const getRecentMemories = (limit = 20) => fetchAPI(`/memories/recent?limit=${limit}`)
export const createMemory = (data) => fetchAPI('/memories', {
  method: 'POST', body: JSON.stringify(data),
})

// ── People ────────────────────────────────────────────────────
export const getPeople = () => fetchAPI('/people')
export const getPerson = (name) => fetchAPI(`/people/${encodeURIComponent(name)}`)
export const upsertPerson = (data) => fetchAPI('/people', {
  method: 'POST', body: JSON.stringify(data),
})

// ── Tasks ─────────────────────────────────────────────────────
export const getTasks = (module) => fetchAPI(`/tasks${module ? `?module=${module}` : ''}`)
export const createTask = (data) => fetchAPI('/tasks', {
  method: 'POST', body: JSON.stringify(data),
})
export const completeTask = (id) => fetchAPI(`/tasks/${id}/complete`, { method: 'POST' })

// ── Trades ────────────────────────────────────────────────────
export const getTrades = (limit = 50) => fetchAPI(`/trades?limit=${limit}`)
export const getOpenTrades = () => fetchAPI('/trades/open')

// ── Actions ───────────────────────────────────────────────────
export const getActions = (date) => fetchAPI(`/actions${date ? `?date=${date}` : ''}`)

// ── Costs ─────────────────────────────────────────────────────
export const getCosts = (period = 'today') => fetchAPI(`/costs?period=${period}`)

// ── Settings ──────────────────────────────────────────────────
export const getSettingsSchema = () => fetchAPI('/settings/schema')
export const getSettings = () => fetchAPI('/settings')
export const updateSetting = (key, value) => fetchAPI('/settings', {
  method: 'POST', body: JSON.stringify({ key, value: String(value) }),
})

// ── Rules ─────────────────────────────────────────────────────
export const getRules = () => fetchAPI('/rules')
export const updateRule = (key, value) => fetchAPI(`/rules/${key}`, {
  method: 'POST', body: JSON.stringify({ key, value }),
})

// ── Calendar ──────────────────────────────────────────────────
export const getCalendarEvents = (start, end) => {
  const params = new URLSearchParams()
  if (start) params.set('start', start)
  if (end) params.set('end', end)
  return fetchAPI(`/calendar/events?${params}`)
}
export const getMiraSchedule = () => fetchAPI('/calendar/schedule')

// ── Kill Switch ──────────────────────────────────────────────
export const getKillSwitchStatus = () => fetchAPI('/killswitch/status')
export const activateKillSwitch = () => fetchAPI('/killswitch', { method: 'POST' })
export const deactivateKillSwitch = () => fetchAPI('/resume', { method: 'POST' })

// ── Earnings ─────────────────────────────────────────────────
export const getEarnings = () => fetchAPI('/earnings')

// ── Modules ───────────────────────────────────────────────────
export const getModules = () => fetchAPI('/modules')
