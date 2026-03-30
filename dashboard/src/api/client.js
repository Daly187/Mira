/**
 * Mira API client — connects dashboard to the FastAPI backend.
 * Supports remote access: backend URL stored in localStorage.
 * Token auth for secure API access.
 */

function getApiBase() {
  const backendUrl = localStorage.getItem('mira_backend_url')
  if (backendUrl) {
    // Remote mode: full URL to the backend (e.g., https://mira.example.com)
    return backendUrl.replace(/\/+$/, '') + '/api'
  }
  // Local mode: same-origin (FastAPI serves both dashboard and API)
  return '/api'
}

async function fetchAPI(endpoint, options = {}) {
  const token = localStorage.getItem('mira_api_token')
  const apiBase = getApiBase()

  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${apiBase}${endpoint}`, { ...options, headers })

  // If 401, redirect to login (unless already on login/setup)
  if (response.status === 401) {
    const path = window.location.pathname
    if (path !== '/login' && !path.startsWith('/setup')) {
      localStorage.removeItem('mira_api_token')
      window.location.href = '/login'
      throw new Error('Authentication required')
    }
  }

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

// ── Habits ───────────────────────────────────────────────────
export const getHabits = () => fetchAPI('/habits')
export const logHabit = (name) => fetchAPI(`/habits/${encodeURIComponent(name)}/log`, {
  method: 'POST',
})

// ── Relationships ────────────────────────────────────────────
export const getRelationshipHealth = () => fetchAPI('/relationships/health')

// ── Schedule ─────────────────────────────────────────────────
export const getScheduleHistory = () => fetchAPI('/schedule')

// ── Decisions ────────────────────────────────────────────────
export const getDecisions = (limit = 50) => fetchAPI(`/decisions?limit=${limit}`)
export const scoreDecision = (id, score, outcome) => fetchAPI(`/decisions/${id}/score`, {
  method: 'POST', body: JSON.stringify({ score, outcome }),
})

// ── Compliance ───────────────────────────────────────────────
export const getComplianceDeadlines = () => fetchAPI('/compliance/deadlines')
export const addComplianceDeadline = (data) => fetchAPI('/compliance/deadlines', {
  method: 'POST', body: JSON.stringify(data),
})

// ── Earnings ─────────────────────────────────────────────────
export const getEarnings = () => fetchAPI('/earnings')

// ── Modules ───────────────────────────────────────────────────
export const getModules = () => fetchAPI('/modules')

// ── Setup / API Key Management ───────────────────────────────
export const getSetupStatus = () => fetchAPI('/setup/status')
export const saveSetupKeys = (keys) => fetchAPI('/setup/keys', {
  method: 'POST', body: JSON.stringify({ keys }),
})
export const testSetupService = (service) => fetchAPI(`/setup/test/${service}`, {
  method: 'POST',
})

// ── Auth ─────────────────────────────────────────────────────
export const setBackendUrl = (url) => {
  if (url) {
    localStorage.setItem('mira_backend_url', url.replace(/\/+$/, ''))
  } else {
    localStorage.removeItem('mira_backend_url')
  }
}

export const getBackendUrl = () => localStorage.getItem('mira_backend_url') || ''

export const checkAuth = async () => {
  try {
    const token = localStorage.getItem('mira_api_token')
    const apiBase = getApiBase()
    const res = await fetch(`${apiBase}/health`, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {}
    })
    if (!res.ok) return false
    const data = await res.json()
    // If no auth required, auto-login
    if (!data.auth_required) return true
    // If auth required, check if we have a valid token
    if (!token) return false
    const statusRes = await fetch(`${apiBase}/status`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    return statusRes.ok
  } catch { return false }
}

export const login = (token) => localStorage.setItem('mira_api_token', token)
export const logout = () => {
  localStorage.removeItem('mira_api_token')
  localStorage.removeItem('mira_backend_url')
  window.location.href = '/login'
}
export const isLoggedIn = () => !!localStorage.getItem('mira_api_token')

// ── WebSocket ────────────────────────────────────────────────
let _ws = null
let _wsListeners = new Set()
let _wsReconnectTimer = null

/**
 * Connect to the Mira WebSocket for real-time updates.
 * Supports remote backend via stored URL.
 */
export function connectWS() {
  if (_ws && _ws.readyState <= 1) return // already connected or connecting

  const token = localStorage.getItem('mira_api_token') || ''
  const backendUrl = localStorage.getItem('mira_backend_url')

  let url
  if (backendUrl) {
    // Remote mode: derive WebSocket URL from backend URL
    const parsed = new URL(backendUrl)
    const proto = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
    url = `${proto}//${parsed.host}/ws?token=${encodeURIComponent(token)}`
  } else {
    // Local mode: same host
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    url = `${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`
  }

  _ws = new WebSocket(url)

  _ws.onopen = () => {
    console.log('[Mira WS] Connected')
    if (_wsReconnectTimer) {
      clearTimeout(_wsReconnectTimer)
      _wsReconnectTimer = null
    }
  }

  _ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'ping') {
        _ws.send('ping')
        return
      }
      _wsListeners.forEach((fn) => fn(data))
    } catch (e) {
      console.warn('[Mira WS] Bad message:', e)
    }
  }

  _ws.onclose = () => {
    console.log('[Mira WS] Disconnected, reconnecting in 5s...')
    _ws = null
    _wsReconnectTimer = setTimeout(connectWS, 5000)
  }

  _ws.onerror = () => {
    _ws?.close()
  }
}

export function onWSEvent(listener) {
  _wsListeners.add(listener)
  return () => _wsListeners.delete(listener)
}

export function disconnectWS() {
  if (_wsReconnectTimer) {
    clearTimeout(_wsReconnectTimer)
    _wsReconnectTimer = null
  }
  if (_ws) {
    _ws.close()
    _ws = null
  }
  _wsListeners.clear()
}
