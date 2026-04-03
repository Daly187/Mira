import { useState, useEffect, useCallback } from 'react'
import {
  Shield, ShieldOff, ShieldAlert, AlertTriangle, Play, Pause,
  Bot, MessageSquare, TrendingUp, Mail, Globe, Zap, RefreshCw
} from 'lucide-react'
import { getKillSwitchStatus, activateKillSwitch, deactivateKillSwitch } from '../api/client'

const PAUSED_ITEMS = [
  { icon: Bot, label: 'Autonomous agent loop', desc: 'Mira stops executing scheduled tasks and self-directed actions' },
  { icon: TrendingUp, label: 'Trading operations', desc: 'All open orders held, no new trades placed' },
  { icon: Globe, label: 'Social media posting', desc: 'Queued posts across all 6 platforms are paused' },
  { icon: Mail, label: 'Email & calendar actions', desc: 'No emails sent, no calendar events created' },
  { icon: MessageSquare, label: 'Auto-replies', desc: 'Telegram and WhatsApp auto-responses disabled' },
  { icon: Zap, label: 'Earning tasks', desc: 'All revenue-generating automation paused' },
]

export default function KillSwitchPage() {
  const [active, setActive] = useState(false)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)
  const [error, setError] = useState(null)
  const [showConfirm, setShowConfirm] = useState(null) // 'activate' | 'deactivate' | null
  const [lastChanged, setLastChanged] = useState(null)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getKillSwitchStatus()
      setActive(data.active ?? data.killed ?? false)
      if (data.changed_at || data.timestamp) {
        setLastChanged(data.changed_at || data.timestamp)
      }
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleToggle = async () => {
    setToggling(true)
    setError(null)
    try {
      if (active) {
        await deactivateKillSwitch()
        setActive(false)
      } else {
        await activateKillSwitch()
        setActive(true)
      }
      setLastChanged(new Date().toISOString())
    } catch (e) {
      setError(e.message)
    } finally {
      setToggling(false)
      setShowConfirm(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <RefreshCw className="animate-spin text-gray-500" size={32} />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Shield className="text-mira-500" size={28} />
        <div>
          <h1 className="text-2xl font-bold text-white">Kill Switch</h1>
          <p className="text-sm text-gray-500">Emergency control over all autonomous operations</p>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3 text-red-400 text-sm">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      {/* Status card */}
      <div className={`rounded-2xl border p-8 text-center space-y-6 transition-colors ${
        active
          ? 'bg-red-500/5 border-red-500/30'
          : 'bg-emerald-500/5 border-emerald-500/30'
      }`}>
        {/* Status icon */}
        <div className="flex justify-center">
          <div className={`w-24 h-24 rounded-full flex items-center justify-center ${
            active ? 'bg-red-500/20' : 'bg-emerald-500/20'
          }`}>
            {active
              ? <ShieldAlert className="text-red-400" size={48} />
              : <ShieldOff className="text-emerald-400" size={48} />
            }
          </div>
        </div>

        {/* Status text */}
        <div>
          <p className={`text-3xl font-bold ${active ? 'text-red-400' : 'text-emerald-400'}`}>
            {active ? 'KILL SWITCH ACTIVE' : 'ALL SYSTEMS RUNNING'}
          </p>
          <p className="text-gray-500 mt-2 text-sm">
            {active
              ? 'All autonomous operations are paused. Mira is in manual-only mode.'
              : 'Mira is operating normally with full autonomy.'}
          </p>
          {lastChanged && (
            <p className="text-gray-600 text-xs mt-2">
              Last changed: {new Date(lastChanged).toLocaleString()}
            </p>
          )}
        </div>

        {/* Toggle button */}
        <div>
          <button
            onClick={() => setShowConfirm(active ? 'deactivate' : 'activate')}
            disabled={toggling}
            className={`inline-flex items-center gap-3 px-8 py-4 rounded-xl text-lg font-semibold transition-all ${
              active
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                : 'bg-red-600 hover:bg-red-500 text-white'
            } ${toggling ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {toggling ? (
              <RefreshCw className="animate-spin" size={22} />
            ) : active ? (
              <Play size={22} />
            ) : (
              <Pause size={22} />
            )}
            {active ? 'Resume All Operations' : 'Activate Kill Switch'}
          </button>
        </div>
      </div>

      {/* Confirmation dialog */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-md w-full space-y-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className={showConfirm === 'activate' ? 'text-red-400' : 'text-emerald-400'} size={24} />
              <h2 className="text-lg font-bold text-white">
                {showConfirm === 'activate' ? 'Activate Kill Switch?' : 'Resume Operations?'}
              </h2>
            </div>
            <p className="text-gray-400 text-sm">
              {showConfirm === 'activate'
                ? 'This will immediately pause ALL autonomous operations. Mira will only respond to manual commands until you resume.'
                : 'This will restore full autonomous operation. Mira will resume all scheduled tasks, trading, posting, and other automated actions.'}
            </p>
            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => setShowConfirm(null)}
                className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 border border-gray-700 hover:border-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleToggle}
                disabled={toggling}
                className={`px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors ${
                  showConfirm === 'activate'
                    ? 'bg-red-600 hover:bg-red-500'
                    : 'bg-emerald-600 hover:bg-emerald-500'
                } ${toggling ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {toggling
                  ? 'Processing...'
                  : showConfirm === 'activate'
                    ? 'Yes, Activate Kill Switch'
                    : 'Yes, Resume Operations'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* What gets paused */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          What gets paused when Kill Switch is active
        </h2>
        <div className="space-y-3">
          {PAUSED_ITEMS.map(({ icon: Icon, label, desc }) => (
            <div key={label} className="flex items-start gap-3">
              <div className={`mt-0.5 p-1.5 rounded-lg ${active ? 'bg-red-500/10' : 'bg-gray-800'}`}>
                <Icon size={16} className={active ? 'text-red-400' : 'text-gray-500'} />
              </div>
              <div>
                <p className="text-sm text-gray-200">{label}</p>
                <p className="text-xs text-gray-600">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Info note */}
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 text-xs text-gray-600">
        <p>
          The kill switch can also be triggered via Telegram with <code className="text-mira-400">/killswitch</code> and
          resumed with <code className="text-mira-400">/resume</code>. Status is synced in real-time.
        </p>
      </div>
    </div>
  )
}
