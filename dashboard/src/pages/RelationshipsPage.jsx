import { useState, useEffect } from 'react'
import { Heart, AlertTriangle, Clock, MessageCircle, Users } from 'lucide-react'
import { getPeople, getRelationshipHealth } from '../api/client'

const healthColors = {
  good: 'text-green-400',
  neutral: 'text-gray-400',
  needs_attention: 'text-yellow-400',
  at_risk: 'text-red-400',
}

const healthBg = {
  good: 'bg-green-500/10 border-green-500/30',
  neutral: 'bg-gray-500/10 border-gray-500/30',
  needs_attention: 'bg-yellow-500/10 border-yellow-500/30',
  at_risk: 'bg-red-500/10 border-red-500/30',
}

export default function RelationshipsPage() {
  const [people, setPeople] = useState([])
  const [flagged, setFlagged] = useState([])
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('all') // 'all' | 'flagged'

  useEffect(() => {
    Promise.all([getPeople(), getRelationshipHealth()])
      .then(([p, f]) => {
        setPeople(p || [])
        setFlagged(f || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const daysSince = (dateStr) => {
    if (!dateStr) return null
    const d = new Date(dateStr)
    const now = new Date()
    return Math.floor((now - d) / 86400000)
  }

  // Group people by relationship type
  const grouped = {}
  people.forEach((p) => {
    const type = p.relationship_type || 'unknown'
    if (!grouped[type]) grouped[type] = []
    grouped[type].push(p)
  })

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Relationships</h1>
      <p className="text-gray-500 text-sm mb-8">CRM + relationship health monitoring</p>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Total Contacts</p>
              <p className="text-2xl font-bold mt-1">{people.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Need Attention</p>
              <p className="text-2xl font-bold mt-1 text-yellow-400">
                {flagged.filter((f) => f.relationship_health === 'needs_attention').length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">At Risk</p>
              <p className="text-2xl font-bold mt-1 text-red-400">
                {flagged.filter((f) => f.relationship_health === 'at_risk').length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Types</p>
              <p className="text-2xl font-bold mt-1 text-mira-400">
                {Object.keys(grouped).length}
              </p>
            </div>
          </div>

          {/* View toggle */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setView('all')}
              className={`px-4 py-2 rounded-lg text-sm transition ${
                view === 'all'
                  ? 'bg-mira-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
            >
              <Users size={14} className="inline mr-2" />
              All Contacts ({people.length})
            </button>
            <button
              onClick={() => setView('flagged')}
              className={`px-4 py-2 rounded-lg text-sm transition ${
                view === 'flagged'
                  ? 'bg-mira-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
            >
              <AlertTriangle size={14} className="inline mr-2" />
              Needs Attention ({flagged.length})
            </button>
          </div>

          {/* Flagged view */}
          {view === 'flagged' && (
            <div className="space-y-4">
              {flagged.length === 0 ? (
                <div className="text-center py-12 text-gray-600">
                  <Heart size={48} className="mx-auto mb-4 opacity-30" />
                  <p>All relationships are healthy.</p>
                </div>
              ) : (
                flagged.map((person, i) => {
                  const health = person.relationship_health || 'neutral'
                  return (
                    <div
                      key={i}
                      className={`border rounded-xl p-4 ${healthBg[health] || healthBg.neutral}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <h3 className="font-semibold text-gray-200">{person.name}</h3>
                          <span className="text-xs text-gray-500">{person.relationship_type}</span>
                        </div>
                        <span className={`text-sm font-medium ${healthColors[health]}`}>
                          {health.replace('_', ' ').toUpperCase()}
                        </span>
                      </div>
                      <div className="flex gap-6 text-xs text-gray-400 mt-2">
                        <span className="flex items-center gap-1">
                          <Clock size={12} />
                          {person.last_interaction
                            ? `${daysSince(person.last_interaction)}d ago`
                            : 'Never'}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle size={12} />
                          {person.conversation_count || 0} conversations
                        </span>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}

          {/* All contacts view */}
          {view === 'all' && (
            <div>
              {Object.entries(grouped)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([type, contacts]) => (
                  <div key={type} className="mb-6">
                    <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                      {type.replace('_', ' ')} ({contacts.length})
                    </h2>
                    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-gray-500 text-xs uppercase bg-gray-800/50">
                            <th className="text-left px-4 py-3">Name</th>
                            <th className="text-center px-4 py-3">Last Contact</th>
                            <th className="text-center px-4 py-3">Conversations</th>
                            <th className="text-center px-4 py-3">Health</th>
                            <th className="text-left px-4 py-3">Email</th>
                          </tr>
                        </thead>
                        <tbody>
                          {contacts.map((person, i) => {
                            const days = daysSince(person.last_interaction)
                            const health = person.relationship_health || 'neutral'
                            return (
                              <tr key={i} className="border-t border-gray-800">
                                <td className="px-4 py-3 font-medium text-gray-200">
                                  {person.name}
                                </td>
                                <td className="px-4 py-3 text-center text-gray-400">
                                  {days !== null ? (
                                    <span className={days > 30 ? 'text-yellow-400' : ''}>
                                      {days}d ago
                                    </span>
                                  ) : (
                                    <span className="text-gray-600">—</span>
                                  )}
                                </td>
                                <td className="px-4 py-3 text-center text-gray-400">
                                  {person.conversation_count || 0}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  <span
                                    className={`text-xs px-2 py-0.5 rounded-full ${
                                      health === 'good'
                                        ? 'bg-green-500/20 text-green-400'
                                        : health === 'at_risk'
                                        ? 'bg-red-500/20 text-red-400'
                                        : health === 'needs_attention'
                                        ? 'bg-yellow-500/20 text-yellow-400'
                                        : 'bg-gray-500/20 text-gray-400'
                                    }`}
                                  >
                                    {health.replace('_', ' ')}
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-gray-500 text-xs">
                                  {person.email || '—'}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
