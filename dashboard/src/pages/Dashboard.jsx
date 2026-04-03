import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Brain, Users, TrendingUp, DollarSign, Activity, Zap, Target, Clock, ShieldOff, ShieldCheck, AlertTriangle, Calendar, Heart } from 'lucide-react'
import { getKPIs, getRecentMemories, getActions, getKillSwitchStatus, activateKillSwitch, deactivateKillSwitch, getSetupStatus, getHabits, getScheduleHistory, getOpenTrades } from '../api/client'

function KPICard({ icon: Icon, label, value, sub, color = 'text-mira-400' }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg bg-gray-800 ${color}`}>
          <Icon size={18} />
        </div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-100">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [kpis, setKpis] = useState(null)
  const [memories, setMemories] = useState([])
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [habits, setHabits] = useState([])
  const [scheduleTasks, setScheduleTasks] = useState([])
  const [openTrades, setOpenTrades] = useState([])
  const [killSwitchActive, setKillSwitchActive] = useState(false)
  const [showKillConfirm, setShowKillConfirm] = useState(false)
  const [killSwitchLoading, setKillSwitchLoading] = useState(false)
  const [setupNeeded, setSetupNeeded] = useState(false)
  const [setupDismissed, setSetupDismissed] = useState(false)
  const [backendError, setBackendError] = useState(null)

  useEffect(() => {
    getSetupStatus().then(s => setSetupNeeded(!s.setup_complete)).catch(() => {})
  }, [])

  useEffect(() => {
    async function load() {
      try {
        const [k, m, a, ks, h, st, ot] = await Promise.all([
          getKPIs(),
          getRecentMemories(5),
          getActions(),
          getKillSwitchStatus(),
          getHabits().catch(() => []),
          getScheduleHistory().catch(() => []),
          getOpenTrades().catch(() => []),
        ])
        setKpis(k)
        setMemories(m)
        setActions(a)
        setKillSwitchActive(ks.kill_switch_active)
        setHabits(h)
        setScheduleTasks(st)
        setOpenTrades(ot)
      } catch (e) {
        console.error('Failed to load dashboard:', e)
        setBackendError(e.message)
      }
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  async function handleKillSwitch() {
    if (!killSwitchActive) {
      setShowKillConfirm(true)
      return
    }
    setKillSwitchLoading(true)
    try {
      await deactivateKillSwitch()
      setKillSwitchActive(false)
    } catch (e) {
      console.error('Failed to toggle kill switch:', e)
    }
    setKillSwitchLoading(false)
  }

  async function confirmKillSwitch() {
    setKillSwitchLoading(true)
    setShowKillConfirm(false)
    try {
      await activateKillSwitch()
      setKillSwitchActive(true)
    } catch (e) {
      console.error('Failed to activate kill switch:', e)
    }
    setKillSwitchLoading(false)
  }

  if (loading) {
    return <div className="text-gray-500">Loading dashboard...</div>
  }

  if (!kpis) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl text-gray-400 mb-2">Cannot connect to Mira backend</h2>
        <p className="text-gray-600 max-w-md mx-auto">
          {backendError || 'Make sure the FastAPI server is running and configure the backend URL in Settings.'}
        </p>
        <Link to="/settings" className="inline-block mt-4 bg-purple-600 hover:bg-purple-700 text-white px-6 py-2 rounded-lg text-sm transition">
          Configure Backend
        </Link>
      </div>
    )
  }

  return (
    <div>
      {/* Setup Needed Banner */}
      {setupNeeded && !setupDismissed && (
        <div className="mb-6 bg-gradient-to-r from-purple-900/50 to-amber-900/30 border border-purple-500/30 rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <div>
              <span className="text-sm font-medium text-white">Mira needs API keys to get started</span>
              <span className="text-xs text-gray-400 ml-2">Configure your Anthropic and Telegram keys</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/setup" className="bg-purple-600 hover:bg-purple-500 text-white text-sm px-4 py-1.5 rounded-lg">
              Go to Setup &rarr;
            </Link>
            <button onClick={() => setSetupDismissed(true)} className="text-gray-500 hover:text-gray-300 text-sm">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Kill Switch Confirmation Dialog */}
      {showKillConfirm && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
          <div className="bg-gray-900 border border-red-800 rounded-xl p-6 max-w-md mx-4">
            <h3 className="text-xl font-bold text-red-400 mb-3">Activate Kill Switch?</h3>
            <p className="text-gray-300 mb-6">
              This will immediately pause ALL autonomous actions. Mira will enter listen-only mode.
              Trading, social posting, emails, and all automated tasks will stop.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowKillConfirm(false)}
                className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmKillSwitch}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors font-medium"
              >
                Activate Kill Switch
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Kill Switch Banner */}
      {killSwitchActive && (
        <div className="mb-4 p-4 bg-red-900/30 border border-red-800/50 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldOff size={24} className="text-red-400" />
            <div>
              <span className="text-red-400 font-bold text-lg">PAUSED</span>
              <p className="text-red-300/70 text-sm">All autonomous actions are suspended</p>
            </div>
          </div>
          <button
            onClick={handleKillSwitch}
            disabled={killSwitchLoading}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors font-medium disabled:opacity-50"
          >
            {killSwitchLoading ? 'Resuming...' : 'Resume Operations'}
          </button>
        </div>
      )}

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Mira's operational overview</p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handleKillSwitch}
            disabled={killSwitchLoading}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 ${
              killSwitchActive
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-red-900/50 border border-red-800 hover:bg-red-800 text-red-400'
            }`}
          >
            {killSwitchActive ? <ShieldCheck size={18} /> : <ShieldOff size={18} />}
            {killSwitchLoading ? '...' : killSwitchActive ? 'Resume' : 'Kill Switch'}
          </button>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
            killSwitchActive
              ? 'bg-red-900/30 border border-red-800/50'
              : 'bg-green-900/30 border border-green-800/50'
          }`}>
            <div className={`w-2 h-2 rounded-full animate-pulse ${
              killSwitchActive ? 'bg-red-400' : 'bg-green-400'
            }`} />
            <span className={`text-sm font-medium ${
              killSwitchActive ? 'text-red-400' : 'text-green-400'
            }`}>
              {killSwitchActive ? 'PAUSED' : 'ACTIVE'}
            </span>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPICard
          icon={Brain}
          label="Memories"
          value={kpis.memory.total_memories}
          sub={`${kpis.memory.total_people} people tracked`}
        />
        <KPICard
          icon={TrendingUp}
          label="Trading P&L"
          value={`$${kpis.trading.total_pnl}`}
          sub={`${kpis.trading.win_rate}% win rate (${kpis.trading.total_trades} trades)`}
          color="text-green-400"
        />
        <KPICard
          icon={DollarSign}
          label="API Cost Today"
          value={`$${kpis.api_costs.today.toFixed(4)}`}
          sub={`$${kpis.api_costs.month.toFixed(2)} this month (${kpis.api_costs.calls_today} calls)`}
          color="text-yellow-400"
        />
        <KPICard
          icon={Activity}
          label="Actions Today"
          value={kpis.activity.actions_today}
          sub={`${kpis.activity.pending_tasks} tasks pending`}
          color="text-blue-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Recent Memories */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Brain size={18} className="text-mira-400" />
            Recent Memories
          </h3>
          <div className="space-y-3">
            {memories.length === 0 ? (
              <p className="text-gray-600 text-sm">No memories yet. Start talking to Mira.</p>
            ) : (
              memories.map((m) => (
                <div key={m.id} className="border-b border-gray-800 pb-3 last:border-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 bg-mira-500/20 text-mira-300 rounded-full">
                      {m.category}
                    </span>
                    <span className="text-xs text-gray-600">
                      importance: {m.importance}/5
                    </span>
                  </div>
                  <p className="text-sm text-gray-300">{m.content?.slice(0, 150)}</p>
                  <p className="text-xs text-gray-600 mt-1">{m.created_at}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Actions */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap size={18} className="text-yellow-400" />
            Today's Actions
          </h3>
          <div className="space-y-2">
            {actions.length === 0 ? (
              <p className="text-gray-600 text-sm">No actions yet today.</p>
            ) : (
              actions.slice(-10).reverse().map((a) => (
                <div key={a.id} className="flex items-center gap-3 text-sm py-2 border-b border-gray-800/50 last:border-0">
                  <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded font-mono">
                    {a.module}
                  </span>
                  <span className="text-gray-300 flex-1">{a.action}</span>
                  <span className="text-xs text-gray-600">{a.created_at?.split('T')[1]?.slice(0,5)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom row — 3 quick widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Habits Today */}
        <Link to="/habits" className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-gray-400 uppercase tracking-wider">
            <Target size={14} className="text-purple-400" />
            Habits Today
          </h3>
          {habits.length === 0 ? (
            <p className="text-gray-600 text-sm">No habits tracked yet.</p>
          ) : (
            <div className="space-y-2">
              {habits.slice(0, 5).map((h) => {
                const today = new Date().toISOString().slice(0, 10)
                const done = h.last_completed === today
                return (
                  <div key={h.id} className="flex items-center justify-between">
                    <span className={`text-sm ${done ? 'text-green-400 line-through' : 'text-gray-300'}`}>
                      {h.name}
                    </span>
                    <span className="text-xs text-gray-600">{h.streak}d streak</span>
                  </div>
                )
              })}
              {habits.length > 5 && (
                <p className="text-xs text-gray-600">+{habits.length - 5} more</p>
              )}
            </div>
          )}
        </Link>

        {/* Open Trades */}
        <Link to="/trades" className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-gray-400 uppercase tracking-wider">
            <TrendingUp size={14} className="text-green-400" />
            Open Positions
          </h3>
          {openTrades.length === 0 ? (
            <p className="text-gray-600 text-sm">No open positions.</p>
          ) : (
            <div className="space-y-2">
              {openTrades.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">
                    <span className={t.direction === 'buy' ? 'text-green-400' : 'text-red-400'}>
                      {t.direction?.toUpperCase()}
                    </span>{' '}
                    {t.instrument}
                  </span>
                  <span className="text-xs text-gray-600">{t.size} @ {t.entry_price}</span>
                </div>
              ))}
              {openTrades.length > 5 && (
                <p className="text-xs text-gray-600">+{openTrades.length - 5} more</p>
              )}
            </div>
          )}
        </Link>

        {/* Recent Schedule Activity */}
        <Link to="/schedule" className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-gray-400 uppercase tracking-wider">
            <Clock size={14} className="text-blue-400" />
            Autonomous Tasks
          </h3>
          {scheduleTasks.length === 0 ? (
            <p className="text-gray-600 text-sm">No scheduled tasks loaded.</p>
          ) : (() => {
            const recentlyRun = scheduleTasks.filter(t => {
              if (!t.last_run) return false
              return Date.now() - new Date(t.last_run).getTime() < 86400000
            })
            const neverRun = scheduleTasks.filter(t => !t.last_run)
            return (
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Total tasks</span>
                  <span className="text-sm font-medium text-gray-200">{scheduleTasks.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Run today</span>
                  <span className="text-sm font-medium text-green-400">{recentlyRun.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">Never run</span>
                  <span className="text-sm font-medium text-yellow-400">{neverRun.length}</span>
                </div>
              </div>
            )
          })()}
        </Link>
      </div>
    </div>
  )
}
