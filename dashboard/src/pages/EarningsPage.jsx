import { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Clock, Zap, AlertTriangle, RefreshCw, Briefcase, BarChart3 } from 'lucide-react'
import { getEarnings } from '../api/client'

const TIMEOUT_MS = 5000

const STREAM_ICONS = {
  affiliate: Briefcase,
  freelance: Briefcase,
  trading: TrendingUp,
  content: BarChart3,
  saas: Zap,
}

function StatusBadge({ status }) {
  const styles = {
    active: 'bg-green-900/30 text-green-400 border-green-800/50',
    pending: 'bg-yellow-900/30 text-yellow-400 border-yellow-800/50',
    paused: 'bg-gray-900/30 text-gray-400 border-gray-800/50',
  }
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${styles[status] || styles.pending}`}>
      {status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Pending'}
    </span>
  )
}

function EarningCard({ module }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-100">{module.name}</h3>
        <StatusBadge status={module.status} />
      </div>
      <p className="text-sm text-gray-400 mb-4">{module.description}</p>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <p className="text-xs text-gray-500">Potential</p>
          <p className="text-sm font-medium text-gray-200">
            ${(module.potential_min || 0).toLocaleString()} - ${(module.potential_max || 0).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Phase</p>
          <p className="text-sm font-medium text-gray-200">Phase {module.phase || '--'}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">This Month</p>
          <p className={`text-sm font-medium ${(module.current_month_earnings || 0) > 0 ? 'text-green-400' : 'text-gray-500'}`}>
            ${(module.current_month_earnings || 0).toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function EarningsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchEarnings = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await Promise.race([
        getEarnings(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Request timed out after 5 seconds')), TIMEOUT_MS)),
      ])
      setData(result)
    } catch (e) {
      console.error('Failed to load earnings:', e)
      setError(e.message || 'Failed to load earnings data')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEarnings()
  }, [])

  const activeCount = data?.modules?.filter(m => m.status === 'active').length || 0
  const totalModules = data?.modules?.length || 0

  // Group modules by status for the revenue streams section
  const activeModules = data?.modules?.filter(m => m.status === 'active') || []
  const pendingModules = data?.modules?.filter(m => m.status !== 'active') || []

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Earnings</h1>
          <p className="text-gray-500 text-sm mt-1">Revenue streams and earning modules</p>
        </div>
        {error && (
          <button
            onClick={fetchEarnings}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-gray-800 text-gray-400 hover:bg-gray-700 transition"
          >
            <RefreshCw size={14} /> Retry
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-6 mb-8">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle size={20} className="text-red-400" />
            <span className="text-red-300 font-medium">Failed to load earnings data</span>
          </div>
          <p className="text-sm text-red-400/80">{error}</p>
          <p className="text-xs text-gray-500 mt-2">Make sure the FastAPI server is running on port 8000.</p>
        </div>
      )}

      {/* Loading state */}
      {loading && !error && (
        <div className="text-center py-16">
          <div className="inline-block w-8 h-8 border-2 border-mira-500 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-gray-500">Loading earnings data...</p>
        </div>
      )}

      {/* Empty state — API responded but no modules */}
      {!loading && !error && data && (!data.modules || data.modules.length === 0) && (
        <div className="text-center py-16">
          <DollarSign size={40} className="mx-auto text-gray-700 mb-4" />
          <h2 className="text-xl text-gray-400 mb-2">No earning modules configured yet</h2>
          <p className="text-gray-600 text-sm max-w-md mx-auto">
            Mira supports 5 revenue streams: affiliate marketing, freelance work, trading, content creation, and SaaS products.
            Modules will appear here as they are activated in later build phases.
          </p>
        </div>
      )}

      {/* Data loaded with content */}
      {!loading && !error && data && data.modules && data.modules.length > 0 && (
        <>
          {/* Summary KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-gray-800 text-green-400">
                  <DollarSign size={18} />
                </div>
                <span className="text-sm text-gray-400">This Month</span>
              </div>
              <div className="text-2xl font-bold text-green-400">
                ${(data.total_current_month || 0).toFixed(2)}
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-gray-800 text-mira-400">
                  <TrendingUp size={18} />
                </div>
                <span className="text-sm text-gray-400">Potential Range</span>
              </div>
              <div className="text-2xl font-bold text-gray-100">
                ${(data.total_potential_min || 0).toLocaleString()} - ${(data.total_potential_max || 0).toLocaleString()}
              </div>
              <p className="text-xs text-gray-500 mt-1">per month across all modules</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-gray-800 text-blue-400">
                  <Zap size={18} />
                </div>
                <span className="text-sm text-gray-400">Active Modules</span>
              </div>
              <div className="text-2xl font-bold text-gray-100">{activeCount} / {totalModules}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-gray-800 text-yellow-400">
                  <Clock size={18} />
                </div>
                <span className="text-sm text-gray-400">Pending Modules</span>
              </div>
              <div className="text-2xl font-bold text-gray-100">{totalModules - activeCount}</div>
            </div>
          </div>

          {/* Revenue Streams Overview */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-8">
            <h3 className="text-lg font-semibold mb-4">Revenue Streams</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-800">
                    <th className="pb-3 pr-4 font-medium">Stream</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 pr-4 font-medium">Phase</th>
                    <th className="pb-3 pr-4 font-medium text-right">This Month</th>
                    <th className="pb-3 font-medium text-right">Potential / mo</th>
                  </tr>
                </thead>
                <tbody>
                  {data.modules.map((mod, i) => (
                    <tr key={mod.id || i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                      <td className="py-3 pr-4 text-gray-200 font-medium">{mod.name}</td>
                      <td className="py-3 pr-4"><StatusBadge status={mod.status} /></td>
                      <td className="py-3 pr-4 text-gray-400">Phase {mod.phase || '--'}</td>
                      <td className={`py-3 pr-4 text-right font-medium ${(mod.current_month_earnings || 0) > 0 ? 'text-green-400' : 'text-gray-500'}`}>
                        ${(mod.current_month_earnings || 0).toFixed(2)}
                      </td>
                      <td className="py-3 text-right text-gray-400">
                        ${(mod.potential_min || 0).toLocaleString()} - ${(mod.potential_max || 0).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Active Module Cards */}
          {activeModules.length > 0 && (
            <>
              <h2 className="text-xl font-semibold mb-4 text-gray-200">Active Modules</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
                {activeModules.map((mod) => (
                  <EarningCard key={mod.id} module={mod} />
                ))}
              </div>
            </>
          )}

          {/* Pending Module Cards */}
          {pendingModules.length > 0 && (
            <>
              <h2 className="text-xl font-semibold mb-4 text-gray-200">Pending Modules</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {pendingModules.map((mod) => (
                  <EarningCard key={mod.id} module={mod} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
