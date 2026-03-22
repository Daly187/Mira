import { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Clock, CheckCircle, Zap } from 'lucide-react'
import { getEarnings } from '../api/client'

function StatusBadge({ status }) {
  const styles = {
    active: 'bg-green-900/30 text-green-400 border-green-800/50',
    pending: 'bg-yellow-900/30 text-yellow-400 border-yellow-800/50',
  }
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${styles[status] || styles.pending}`}>
      {status === 'active' ? 'Active' : 'Pending'}
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
            ${module.potential_min.toLocaleString()} - ${module.potential_max.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Phase</p>
          <p className="text-sm font-medium text-gray-200">Phase {module.phase}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">This Month</p>
          <p className={`text-sm font-medium ${module.current_month_earnings > 0 ? 'text-green-400' : 'text-gray-500'}`}>
            ${module.current_month_earnings.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function EarningsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const earnings = await getEarnings()
        setData(earnings)
      } catch (e) {
        console.error('Failed to load earnings:', e)
      }
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return <div className="text-gray-500">Loading earnings data...</div>
  }

  if (!data) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl text-gray-400 mb-2">Cannot connect to Mira API</h2>
        <p className="text-gray-600">Make sure the FastAPI server is running on port 8000</p>
      </div>
    )
  }

  const activeCount = data.modules.filter(m => m.status === 'active').length

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Earnings</h1>
        <p className="text-gray-500 text-sm mt-1">Revenue streams and earning modules</p>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gray-800 text-green-400">
              <DollarSign size={18} />
            </div>
            <span className="text-sm text-gray-400">This Month</span>
          </div>
          <div className="text-2xl font-bold text-green-400">${data.total_current_month.toFixed(2)}</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gray-800 text-mira-400">
              <TrendingUp size={18} />
            </div>
            <span className="text-sm text-gray-400">Potential Range</span>
          </div>
          <div className="text-2xl font-bold text-gray-100">
            ${data.total_potential_min.toLocaleString()} - ${data.total_potential_max.toLocaleString()}
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
          <div className="text-2xl font-bold text-gray-100">{activeCount} / {data.modules.length}</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gray-800 text-yellow-400">
              <Clock size={18} />
            </div>
            <span className="text-sm text-gray-400">Pending Modules</span>
          </div>
          <div className="text-2xl font-bold text-gray-100">{data.modules.length - activeCount}</div>
        </div>
      </div>

      {/* Module Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.modules.map((mod) => (
          <EarningCard key={mod.id} module={mod} />
        ))}
      </div>
    </div>
  )
}
