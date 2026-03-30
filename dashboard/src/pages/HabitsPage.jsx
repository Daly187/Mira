import { useState, useEffect } from 'react'
import { Target, Check, TrendingUp, TrendingDown, Minus, Plus } from 'lucide-react'
import { getHabits, logHabit } from '../api/client'

const trendIcon = {
  improving: <TrendingUp size={14} className="text-green-400" />,
  declining: <TrendingDown size={14} className="text-red-400" />,
  stable: <Minus size={14} className="text-gray-500" />,
}

export default function HabitsPage() {
  const [habits, setHabits] = useState([])
  const [loading, setLoading] = useState(true)
  const [logging, setLogging] = useState(null)

  const load = () => {
    getHabits()
      .then(setHabits)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleLog = async (name) => {
    setLogging(name)
    try {
      await logHabit(name)
      load()
    } catch (e) {
      console.error(e)
    } finally {
      setLogging(null)
    }
  }

  const today = new Date().toISOString().split('T')[0]

  // Group by category
  const grouped = {}
  habits.forEach((h) => {
    const cat = h.category || 'general'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(h)
  })

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Habits</h1>
      <p className="text-gray-500 text-sm mb-8">Track daily and weekly habits with streaks</p>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : habits.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Target size={48} className="mx-auto mb-4 opacity-30" />
          <p>No habits tracked yet.</p>
          <p className="text-sm mt-2">Use <code className="text-mira-400">/habit add gym</code> in Telegram to start tracking.</p>
        </div>
      ) : (
        <>
          {/* Summary bar */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Total Habits</p>
              <p className="text-2xl font-bold mt-1">{habits.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Done Today</p>
              <p className="text-2xl font-bold mt-1 text-green-400">
                {habits.filter((h) => h.done_today).length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Best Streak</p>
              <p className="text-2xl font-bold mt-1 text-mira-400">
                {Math.max(0, ...habits.map((h) => h.streak || 0))}d
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Remaining</p>
              <p className="text-2xl font-bold mt-1 text-yellow-400">
                {habits.filter((h) => !h.done_today).length}
              </p>
            </div>
          </div>

          {/* Habits by category */}
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category} className="mb-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                {category}
              </h2>
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase bg-gray-800/50">
                      <th className="text-left px-4 py-3">Habit</th>
                      <th className="text-center px-4 py-3">Streak</th>
                      <th className="text-center px-4 py-3">7d</th>
                      <th className="text-center px-4 py-3">Freq</th>
                      <th className="text-center px-4 py-3">Status</th>
                      <th className="text-right px-4 py-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((habit) => (
                      <tr key={habit.id} className="border-t border-gray-800">
                        <td className="px-4 py-3 font-medium text-gray-200">
                          {habit.name}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`font-mono ${habit.streak >= 7 ? 'text-mira-400' : 'text-gray-300'}`}>
                            {habit.streak || 0}d
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center text-gray-400">
                          {habit.completions_7d || 0}/7
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">
                            {habit.target_frequency}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {habit.done_today ? (
                            <span className="inline-flex items-center gap-1 text-green-400 text-xs">
                              <Check size={14} /> Done
                            </span>
                          ) : (
                            <span className="text-gray-600 text-xs">Pending</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {!habit.done_today && (
                            <button
                              onClick={() => handleLog(habit.name)}
                              disabled={logging === habit.name}
                              className="px-3 py-1 bg-mira-500 hover:bg-mira-600 text-white text-xs rounded-lg transition disabled:opacity-50"
                            >
                              {logging === habit.name ? '...' : 'Log'}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
