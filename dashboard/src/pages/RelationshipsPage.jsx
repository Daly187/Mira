import { useState, useEffect } from 'react'
import { Heart, AlertTriangle, Clock, MessageCircle, Users, UserPlus, Info, ShieldAlert } from 'lucide-react'
import { getPeople, getRelationshipHealth, upsertPerson } from '../api/client'

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

const CRITERIA_TEXT = {
  needs_attention: 'No contact in 30+ days',
  at_risk: 'No contact in 60+ days',
}

export default function RelationshipsPage() {
  const [people, setPeople] = useState([])
  const [flagged, setFlagged] = useState([])
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('all') // 'all' | 'flagged' | 'at_risk'
  const [showAddForm, setShowAddForm] = useState(false)
  const [showCriteriaInfo, setShowCriteriaInfo] = useState(false)
  const [newContact, setNewContact] = useState({ name: '', relationship_type: 'friend', email: '', notes: '' })

  const loadData = () => {
    setLoading(true)
    Promise.all([getPeople(), getRelationshipHealth()])
      .then(([p, f]) => {
        setPeople(p || [])
        setFlagged(f || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

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

  const needsAttention = flagged.filter((f) => f.relationship_health === 'needs_attention')
  const atRisk = flagged.filter((f) => f.relationship_health === 'at_risk')

  const handleAddContact = async () => {
    if (!newContact.name.trim()) return
    try {
      await upsertPerson(newContact)
      setShowAddForm(false)
      setNewContact({ name: '', relationship_type: 'friend', email: '', notes: '' })
      loadData()
    } catch (e) {
      console.error('Failed to add contact:', e)
    }
  }

  const renderPersonCard = (person, i) => {
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
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-3xl font-bold">Relationships</h1>
          <p className="text-gray-500 text-sm mt-1">CRM + relationship health monitoring</p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm transition"
        >
          <UserPlus size={16} />
          Add Contact
        </button>
      </div>

      {/* Criteria info banner */}
      <div className="mb-8">
        <button
          onClick={() => setShowCriteriaInfo(!showCriteriaInfo)}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition"
        >
          <Info size={13} />
          <span>How is relationship health determined?</span>
        </button>
        {showCriteriaInfo && (
          <div className="mt-2 bg-gray-900 border border-gray-800 rounded-xl p-4 text-sm text-gray-400">
            <p className="mb-2 text-gray-300 font-medium">Relationship Health Criteria</p>
            <ul className="space-y-1.5">
              <li className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-400" />
                <span><strong className="text-green-400">Good</strong> -- Last contact within 30 days</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-yellow-400" />
                <span><strong className="text-yellow-400">Needs Attention</strong> -- No contact in 30+ days</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-400" />
                <span><strong className="text-red-400">At Risk</strong> -- No contact in 60+ days</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-gray-400" />
                <span><strong className="text-gray-400">Neutral</strong> -- No interaction data recorded yet</span>
              </li>
            </ul>
          </div>
        )}
      </div>

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
                {needsAttention.length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">At Risk</p>
              <p className="text-2xl font-bold mt-1 text-red-400">
                {atRisk.length}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Types</p>
              <p className="text-2xl font-bold mt-1 text-mira-400">
                {Object.keys(grouped).length}
              </p>
            </div>
          </div>

          {/* View toggle — 3 tabs */}
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
                  ? 'bg-yellow-500 text-black'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
            >
              <AlertTriangle size={14} className="inline mr-2" />
              Needs Attention ({needsAttention.length})
            </button>
            <button
              onClick={() => setView('at_risk')}
              className={`px-4 py-2 rounded-lg text-sm transition ${
                view === 'at_risk'
                  ? 'bg-red-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
            >
              <ShieldAlert size={14} className="inline mr-2" />
              At Risk ({atRisk.length})
            </button>
          </div>

          {/* Needs Attention view */}
          {view === 'flagged' && (
            <div className="space-y-4">
              <p className="text-xs text-gray-500 mb-2">
                Contacts with no interaction in 30+ days. Reach out soon to maintain the relationship.
              </p>
              {needsAttention.length === 0 ? (
                <div className="text-center py-12 text-gray-600">
                  <Heart size={48} className="mx-auto mb-4 opacity-30" />
                  <p>No contacts need attention right now.</p>
                </div>
              ) : (
                needsAttention.map((person, i) => renderPersonCard(person, i))
              )}
            </div>
          )}

          {/* At Risk view */}
          {view === 'at_risk' && (
            <div className="space-y-4">
              <p className="text-xs text-gray-500 mb-2">
                Contacts with no interaction in 60+ days. These relationships are fading and need immediate attention.
              </p>
              {atRisk.length === 0 ? (
                <div className="text-center py-12 text-gray-600">
                  <ShieldAlert size={48} className="mx-auto mb-4 opacity-30" />
                  <p>No contacts are at risk. Keep it up!</p>
                </div>
              ) : (
                atRisk.map((person, i) => renderPersonCard(person, i))
              )}
            </div>
          )}

          {/* All contacts view */}
          {view === 'all' && (
            <div>
              {Object.keys(grouped).length === 0 ? (
                <div className="text-center py-12 text-gray-600">
                  <Users size={48} className="mx-auto mb-4 opacity-30" />
                  <p>No contacts yet. Add your first contact above.</p>
                </div>
              ) : (
                Object.entries(grouped)
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
                                      <span className={days > 60 ? 'text-red-400' : days > 30 ? 'text-yellow-400' : ''}>
                                        {days}d ago
                                      </span>
                                    ) : (
                                      <span className="text-gray-600">--</span>
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
                                    {person.email || '--'}
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))
              )}
            </div>
          )}
        </>
      )}

      {/* Add Contact Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowAddForm(false)}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-200">Add Contact</h2>
              <button onClick={() => setShowAddForm(false)} className="text-gray-500 hover:text-gray-300">
                <span className="text-xl leading-none">&times;</span>
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Name</label>
                <input
                  type="text"
                  value={newContact.name}
                  onChange={(e) => setNewContact({ ...newContact, name: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                  placeholder="Contact name..."
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Relationship Type</label>
                <select
                  value={newContact.relationship_type}
                  onChange={(e) => setNewContact({ ...newContact, relationship_type: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                >
                  <option value="friend">Friend</option>
                  <option value="family">Family</option>
                  <option value="colleague">Colleague</option>
                  <option value="client">Client</option>
                  <option value="mentor">Mentor</option>
                  <option value="business">Business</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Email</label>
                <input
                  type="email"
                  value={newContact.email}
                  onChange={(e) => setNewContact({ ...newContact, email: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                  placeholder="Optional email..."
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Notes</label>
                <textarea
                  value={newContact.notes}
                  onChange={(e) => setNewContact({ ...newContact, notes: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500 h-20 resize-none"
                  placeholder="Optional notes..."
                />
              </div>
              <button
                onClick={handleAddContact}
                disabled={!newContact.name.trim()}
                className="w-full bg-mira-500 hover:bg-mira-600 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg py-2 text-sm font-medium transition"
              >
                Add Contact
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
