import { useState, useEffect } from 'react'
import { Clock, CheckCircle, AlertCircle, RefreshCw, Timer, Zap } from 'lucide-react'
import { getScheduleHistory } from '../api/client'

const MODULE_COLORS = {
  pa: 'text-blue-400',
  personal: 'text-purple-400',
  trading: 'text-green-400',
  core: 'text-gray-400',
  patterns: 'text-yellow-400',
  social: 'text-pink-400',
  learning: 'text-cyan-400',
}

function timeAgo(dateStr) {
  if (!dateStr) return 'Never'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function statusBadge(task) {
  if (!task.last_run) {
    return (
      <span className="flex items-center gap-1 text-xs text-gray-500">
        <AlertCircle size={12} />
        Never run
      </span>
    )
  }
  const diff = Date.now() - new Date(task.last_run).getTime()
  const hours = diff / 3600000
  // Determine if it's overdue based on schedule type
  const isInterval = task.schedule.startsWith('Every')
  const isHealthy = isInterval ? hours < 24 : hours < 48
  return (
    <span className={`flex items-center gap-1 text-xs ${isHealthy ? 'text-green-400' : 'text-yellow-400'}`}>
      {isHealthy ? <CheckCircle size={12} /> : <Timer size={12} />}
      {timeAgo(task.last_run)}
    </span>
  )
}

export default function SchedulePage() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    getScheduleHistory()
      .then(setTasks)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const modules = [...new Set(tasks.map((t) => t.module))].sort()
  const filtered = filter === 'all' ? tasks : tasks.filter((t) => t.module === filter)

  // Group by schedule type
  const intervals = filtered.filter((t) => t.schedule.startsWith('Every'))
  const daily = filtered.filter((t) => t.schedule.startsWith('Daily'))
  const weekly = filtered.filter((t) =>
    ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].some((d) =>
      t.schedule.startsWith(d)
    )
  )
  const monthly = filtered.filter((t) => t.schedule.includes('month'))

  const renderGroup = (title, icon, items) => {
    if (items.length === 0) return null
    return (
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          {icon}
          {title} ({items.length})
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase bg-gray-800/50">
                <th className="text-left px-4 py-3">Task</th>
                <th className="text-left px-4 py-3">Module</th>
                <th className="text-left px-4 py-3">Schedule</th>
                <th className="text-center px-4 py-3">Last Run</th>
                <th className="text-left px-4 py-3">Last Outcome</th>
              </tr>
            </thead>
            <tbody>
              {items.map((task) => (
                <tr key={task.name} className="border-t border-gray-800 hover:bg-gray-800/30">
                  <td className="px-4 py-3">
                    <p className="text-gray-200 font-medium">{task.description}</p>
                    <p className="text-xs text-gray-600 font-mono">{task.name}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium uppercase ${MODULE_COLORS[task.module] || 'text-gray-400'}`}>
                      {task.module}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{task.schedule}</td>
                  <td className="px-4 py-3 text-center">{statusBadge(task)}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs max-w-[200px] truncate">
                    {task.last_outcome || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Autonomous Schedule</h1>
      <p className="text-gray-500 text-sm mb-6">All scheduled tasks Mira runs automatically</p>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : tasks.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Clock size={48} className="mx-auto mb-4 opacity-30" />
          <p>No scheduled tasks found.</p>
        </div>
      ) : (
        <>
          {/* Summary bar */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Total Tasks</p>
              <p className="text-2xl font-bold mt-1">{tasks.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Recently Run</p>
              <p className="text-2xl font-bold mt-1 text-green-400">
                {tasks.filter((t) => {
                  if (!t.last_run) return false
                  return Date.now() - new Date(t.last_run).getTime() < 86400000
                }).length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Never Run</p>
              <p className="text-2xl font-bold mt-1 text-yellow-400">
                {tasks.filter((t) => !t.last_run).length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Modules</p>
              <p className="text-2xl font-bold mt-1">{modules.length}</p>
            </div>
          </div>

          {/* Module filter */}
          <div className="flex gap-2 mb-6 flex-wrap">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                filter === 'all'
                  ? 'bg-mira-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              All
            </button>
            {modules.map((mod) => (
              <button
                key={mod}
                onClick={() => setFilter(mod)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  filter === mod
                    ? 'bg-mira-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {mod}
              </button>
            ))}
          </div>

          {renderGroup('Interval Tasks', <RefreshCw size={14} />, intervals)}
          {renderGroup('Daily Tasks', <Clock size={14} />, daily)}
          {renderGroup('Weekly Tasks', <Zap size={14} />, weekly)}
          {renderGroup('Monthly Tasks', <Timer size={14} />, monthly)}
        </>
      )}
    </div>
  )
}
