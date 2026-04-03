import { useState, useEffect } from 'react'
import { Users, UserPlus, Search, Trash2, ArrowUpDown, Filter } from 'lucide-react'
import { getPeople, upsertPerson, deletePerson } from '../api/client'

export default function PeopleCRM() {
  const [people, setPeople] = useState([])
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [filterType, setFilterType] = useState('')
  const [sortBy, setSortBy] = useState('name') // name | last_interaction
  const [sortDir, setSortDir] = useState('asc')
  const [newPerson, setNewPerson] = useState({
    name: '', relationship_type: 'work', email: '', phone: '', company: '', notes: '', birthday: '',
  })

  const relationshipTypes = [
    'work', 'personal', 'family', 'vendor', 'friend', 'colleague', 'client', 'mentor', 'advisor',
  ]

  useEffect(() => {
    getPeople().then(setPeople).catch(console.error)
  }, [])

  const filtered = people
    .filter(p => p.name?.toLowerCase().includes(search.toLowerCase()))
    .filter(p => !filterType || p.relationship_type === filterType)
    .sort((a, b) => {
      let cmp = 0
      if (sortBy === 'name') {
        cmp = (a.name || '').localeCompare(b.name || '')
      } else if (sortBy === 'last_interaction') {
        cmp = (a.last_interaction || '').localeCompare(b.last_interaction || '')
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

  async function handleAdd() {
    if (!newPerson.name.trim()) return
    // Build key_facts from company, notes, birthday
    const facts = []
    if (newPerson.company) facts.push(`Company: ${newPerson.company}`)
    if (newPerson.notes) facts.push(newPerson.notes)
    if (newPerson.birthday) facts.push(`Birthday: ${newPerson.birthday}`)

    await upsertPerson({
      name: newPerson.name,
      relationship_type: newPerson.relationship_type,
      email: newPerson.email || undefined,
      phone: newPerson.phone || undefined,
      key_facts: facts.length > 0 ? facts : undefined,
    })
    setNewPerson({ name: '', relationship_type: 'work', email: '', phone: '', company: '', notes: '', birthday: '' })
    setShowAdd(false)
    setPeople(await getPeople())
  }

  async function handleDelete(person) {
    if (!confirm(`Delete ${person.name}? This cannot be undone.`)) return
    try {
      await deletePerson(person.id)
      setPeople(await getPeople())
    } catch (e) {
      console.error('Failed to delete person:', e)
    }
  }

  function toggleSort(field) {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDir('asc')
    }
  }

  const typeColors = {
    work: 'bg-blue-500/20 text-blue-300',
    personal: 'bg-green-500/20 text-green-300',
    family: 'bg-pink-500/20 text-pink-300',
    vendor: 'bg-orange-500/20 text-orange-300',
    friend: 'bg-cyan-500/20 text-cyan-300',
    colleague: 'bg-indigo-500/20 text-indigo-300',
    client: 'bg-yellow-500/20 text-yellow-300',
    mentor: 'bg-purple-500/20 text-purple-300',
    advisor: 'bg-teal-500/20 text-teal-300',
    unknown: 'bg-gray-500/20 text-gray-300',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">People</h1>
          <p className="text-gray-500 text-sm mt-1">Mira's personal CRM — everyone she knows about</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm"
        >
          <UserPlus size={16} /> Add Person
        </button>
      </div>

      {/* Add Person Form */}
      {showAdd && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <input
              value={newPerson.name}
              onChange={(e) => setNewPerson({ ...newPerson, name: e.target.value })}
              placeholder="Name *"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <select
              value={newPerson.relationship_type}
              onChange={(e) => setNewPerson({ ...newPerson, relationship_type: e.target.value })}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            >
              {relationshipTypes.map(t => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
            <input
              value={newPerson.email}
              onChange={(e) => setNewPerson({ ...newPerson, email: e.target.value })}
              placeholder="Email"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <input
              value={newPerson.phone}
              onChange={(e) => setNewPerson({ ...newPerson, phone: e.target.value })}
              placeholder="Phone"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <input
              value={newPerson.company}
              onChange={(e) => setNewPerson({ ...newPerson, company: e.target.value })}
              placeholder="Company / Organization"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <input
              type="date"
              value={newPerson.birthday}
              onChange={(e) => setNewPerson({ ...newPerson, birthday: e.target.value })}
              placeholder="Birthday"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            />
          </div>
          <textarea
            value={newPerson.notes}
            onChange={(e) => setNewPerson({ ...newPerson, notes: e.target.value })}
            placeholder="Notes (optional)"
            rows={2}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3"
          />
          <div className="flex justify-end">
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 text-gray-400 hover:text-gray-200 text-sm mr-2"
            >
              Cancel
            </button>
            <button onClick={handleAdd} className="px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm">
              Save
            </button>
          </div>
        </div>
      )}

      {/* Search, filter, sort controls */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-2.5 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search people..."
            className="w-full bg-gray-900 border border-gray-800 rounded-lg pl-10 pr-4 py-2 text-sm text-gray-200"
          />
        </div>
        <div className="flex items-center gap-1">
          <Filter size={14} className="text-gray-500" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300"
          >
            <option value="">All types</option>
            {relationshipTypes.map(t => (
              <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1">
          <ArrowUpDown size={14} className="text-gray-500" />
          <button
            onClick={() => toggleSort('name')}
            className={`px-3 py-2 rounded-lg text-sm ${sortBy === 'name' ? 'bg-mira-500/20 text-mira-300' : 'bg-gray-900 border border-gray-800 text-gray-400'}`}
          >
            Name {sortBy === 'name' ? (sortDir === 'asc' ? '\u2191' : '\u2193') : ''}
          </button>
          <button
            onClick={() => toggleSort('last_interaction')}
            className={`px-3 py-2 rounded-lg text-sm ${sortBy === 'last_interaction' ? 'bg-mira-500/20 text-mira-300' : 'bg-gray-900 border border-gray-800 text-gray-400'}`}
          >
            Last seen {sortBy === 'last_interaction' ? (sortDir === 'asc' ? '\u2191' : '\u2193') : ''}
          </button>
        </div>
      </div>

      {/* Results count */}
      <p className="text-xs text-gray-600 mb-3">{filtered.length} contact{filtered.length !== 1 ? 's' : ''} found</p>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Users size={48} className="mx-auto mb-4 opacity-30" />
          <p>{search || filterType ? 'No contacts match your filters.' : 'No people tracked yet. Mira builds this automatically from conversations.'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p) => (
            <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition group">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-gray-200">{p.name}</h3>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${typeColors[p.relationship_type] || typeColors.unknown}`}>
                    {p.relationship_type}
                  </span>
                  <button
                    onClick={() => handleDelete(p)}
                    className="opacity-0 group-hover:opacity-100 transition text-gray-600 hover:text-red-400"
                    title="Delete contact"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {p.email && <p className="text-xs text-gray-500 mb-1">{p.email}</p>}
              {p.phone && <p className="text-xs text-gray-500 mb-1">{p.phone}</p>}
              <div className="text-xs text-gray-600 space-y-1">
                <p>Conversations: {p.conversation_count}</p>
                <p>Last interaction: {p.last_interaction || 'never'}</p>
                {p.key_facts && p.key_facts !== '[]' && (
                  <p className="text-gray-500">Facts: {p.key_facts}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
