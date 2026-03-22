import { useState, useEffect } from 'react'
import { Activity, ChevronLeft, ChevronRight } from 'lucide-react'
import { getActions } from '../api/client'

export default function ActionLog() {
  const [actions, setActions] = useState([])
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    getActions(date).then(setActions).catch(console.error)
  }, [date])

  function prevDay() {
    const d = new Date(date)
    d.setDate(d.getDate() - 1)
    setDate(d.toISOString().split('T')[0])
  }
  function nextDay() {
    const d = new Date(date)
    d.setDate(d.getDate() + 1)
    setDate(d.toISOString().split('T')[0])
  }

  const moduleColors = {
    core: 'bg-gray-500/20 text-gray-300',
    memory: 'bg-mira-500/20 text-mira-300',
    trading: 'bg-green-500/20 text-green-300',
    pa: 'bg-blue-500/20 text-blue-300',
    social: 'bg-pink-500/20 text-pink-300',
    safety: 'bg-red-500/20 text-red-300',
    research: 'bg-yellow-500/20 text-yellow-300',
    settings: 'bg-orange-500/20 text-orange-300',
    rules: 'bg-purple-500/20 text-purple-300',
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Action Log</h1>
      <p className="text-gray-500 text-sm mb-8">Everything Mira did — complete audit trail</p>

      {/* Date navigator */}
      <div className="flex items-center gap-4 mb-6">
        <button onClick={prevDay} className="p-2 bg-gray-800 rounded-lg hover:bg-gray-700">
          <ChevronLeft size={18} />
        </button>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200"
        />
        <button onClick={nextDay} className="p-2 bg-gray-800 rounded-lg hover:bg-gray-700">
          <ChevronRight size={18} />
        </button>
        <span className="text-sm text-gray-500">{actions.length} actions</span>
      </div>

      {/* Action list */}
      {actions.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Activity size={48} className="mx-auto mb-4 opacity-30" />
          <p>No actions recorded for this day.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {actions.map(a => (
            <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex items-center gap-4">
              <div className="text-xs text-gray-500 font-mono w-16 shrink-0">
                {a.created_at?.split('T')[1]?.slice(0, 8) || '--:--'}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${moduleColors[a.module] || moduleColors.core}`}>
                {a.module}
              </span>
              <span className="text-sm text-gray-300 flex-1">{a.action}</span>
              {a.outcome && (
                <span className="text-xs text-gray-500">{a.outcome}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
