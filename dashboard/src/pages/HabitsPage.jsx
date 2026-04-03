import { useState, useEffect } from 'react'
import { Target, Check, Plus, Trash2, Flame, X, AlertCircle } from 'lucide-react'
import { getHabits, logHabit, createHabit, deleteHabit } from '../api/client'

const FREQUENCIES = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekdays', label: 'Weekdays' },
  { value: 'weekly', label: 'Weekly' },
]

const CATEGORIES = ['health', 'productivity', 'learning', 'finance', 'social', 'general']

function StreakBar({ streak }) {
  const dots = 7
  const filled = Math.min(streak, dots)
  return (
    <div className="flex gap-0.5 items-center">
      {Array.from({ length: dots }).map((_, i) => (
        <div
          key={i}
          className={`w-2.5 h-2.5 rounded-sm ${
            i < filled ? 'bg-mira-500' : 'bg-gray-800'
          }`}
        />
      ))}
      {streak > dots && (
        <span className="text-xs text-mira-400 ml-1 font-mono">+{streak - dots}</span>
      )}
    </div>
  )
}

export default function HabitsPage() {
  const [habits, setHabits] = useState([])
  const [loading, setLoading] = useState(true)
  const [logging, setLogging] = useState(null)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [deleting, setDeleting] = useState(null)

  // Form state
  const [formName, setFormName] = useState('')
  const [formFrequency, setFormFrequency] = useState('daily')
  const [formCategory, setFormCategory] = useState('general')
  const [formError, setFormError] = useState(null)
  const [formSubmitting, setFormSubmitting] = useState(false)

  const load = () => {
    setError(null)
    getHabits()
      .then(setHabits)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleLog = async (name) => {
    setLogging(name)
    setError(null)
    try {
      await logHabit(name)
      load()
    } catch (e) {
      setError(`Failed to log "${name}": ${e.message}`)
    } finally {
      setLogging(null)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!formName.trim()) {
      setFormError('Habit name is required')
      return
    }
    setFormSubmitting(true)
    setFormError(null)
    try {
      await createHabit({
        name: formName.trim(),
        target_frequency: formFrequency,
        category: formCategory,
      })
      setFormName('')
      setFormFrequency('daily')
      setFormCategory('general')
      setShowForm(false)
      load()
    } catch (e) {
      setFormError(e.message)
    } finally {
      setFormSubmitting(false)
    }
  }

  const handleDelete = async (habit) => {
    if (deleting === habit.id) return
    setDeleting(habit.id)
    setError(null)
    try {
      await deleteHabit(habit.id)
      load()
    } catch (e) {
      setError(`Failed to delete "${habit.name}": ${e.message}`)
    } finally {
      setDeleting(null)
    }
  }

  // Group by category
  const grouped = {}
  habits.forEach((h) => {
    const cat = h.category || 'general'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(h)
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold">Habits</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white text-sm rounded-lg transition"
        >
          {showForm ? <X size={16} /> : <Plus size={16} />}
          {showForm ? 'Cancel' : 'Add Habit'}
        </button>
      </div>
      <p className="text-gray-500 text-sm mb-6">Track daily and weekly habits with streaks</p>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-800 text-red-300 text-sm rounded-lg px-4 py-3 mb-6">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Add Habit form */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">New Habit</h2>
          {formError && (
            <div className="text-red-400 text-sm mb-3 flex items-center gap-1">
              <AlertCircle size={14} /> {formError}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Habit Name</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. gym, meditation, reading"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-mira-500 focus:outline-none"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Frequency</label>
              <select
                value={formFrequency}
                onChange={(e) => setFormFrequency(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-mira-500 focus:outline-none"
              >
                {FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Category</label>
              <select
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-mira-500 focus:outline-none"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={formSubmitting}
              className="px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white text-sm rounded-lg transition disabled:opacity-50"
            >
              {formSubmitting ? 'Creating...' : 'Create Habit'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : habits.length === 0 ? (
        <div className="text-center py-16 text-gray-600">
          <Target size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg">No habits tracked yet.</p>
          <p className="text-sm mt-2 text-gray-500 mb-4">
            Start building consistency by adding your first habit.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white text-sm rounded-lg transition"
          >
            <Plus size={16} /> Add your first habit
          </button>
        </div>
      ) : (
        <>
          {/* Summary bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
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
                <Flame size={20} className="inline mr-1" />
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
                      <th className="text-right px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((habit) => (
                      <tr key={habit.id} className="border-t border-gray-800 hover:bg-gray-800/30 transition">
                        <td className="px-4 py-3">
                          <span className="font-medium text-gray-200">{habit.name}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col items-center gap-1">
                            <span className={`font-mono text-sm ${habit.streak >= 7 ? 'text-mira-400' : 'text-gray-300'}`}>
                              {habit.streak >= 7 && <Flame size={12} className="inline mr-0.5" />}
                              {habit.streak || 0}d
                            </span>
                            <StreakBar streak={habit.streak || 0} />
                          </div>
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
                          <div className="flex items-center justify-end gap-2">
                            {!habit.done_today && (
                              <button
                                onClick={() => handleLog(habit.name)}
                                disabled={logging === habit.name}
                                className="px-3 py-1 bg-mira-500 hover:bg-mira-600 text-white text-xs rounded-lg transition disabled:opacity-50"
                              >
                                {logging === habit.name ? '...' : 'Log'}
                              </button>
                            )}
                            <button
                              onClick={() => handleDelete(habit)}
                              disabled={deleting === habit.id}
                              className="p-1 text-gray-600 hover:text-red-400 transition disabled:opacity-50"
                              title="Delete habit"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
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
