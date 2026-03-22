import { useState, useEffect } from 'react'
import { Users, UserPlus, Search } from 'lucide-react'
import { getPeople, upsertPerson } from '../api/client'

export default function PeopleCRM() {
  const [people, setPeople] = useState([])
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newPerson, setNewPerson] = useState({ name: '', relationship_type: 'work', email: '' })

  useEffect(() => {
    getPeople().then(setPeople).catch(console.error)
  }, [])

  const filtered = people.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase())
  )

  async function handleAdd() {
    await upsertPerson(newPerson)
    setNewPerson({ name: '', relationship_type: 'work', email: '' })
    setShowAdd(false)
    setPeople(await getPeople())
  }

  const typeColors = {
    work: 'bg-blue-500/20 text-blue-300',
    personal: 'bg-green-500/20 text-green-300',
    family: 'bg-pink-500/20 text-pink-300',
    vendor: 'bg-orange-500/20 text-orange-300',
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

      {showAdd && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <div className="flex items-center gap-3">
            <input
              value={newPerson.name}
              onChange={(e) => setNewPerson({ ...newPerson, name: e.target.value })}
              placeholder="Name"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <select
              value={newPerson.relationship_type}
              onChange={(e) => setNewPerson({ ...newPerson, relationship_type: e.target.value })}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            >
              <option value="work">Work</option>
              <option value="personal">Personal</option>
              <option value="family">Family</option>
              <option value="vendor">Vendor</option>
            </select>
            <input
              value={newPerson.email}
              onChange={(e) => setNewPerson({ ...newPerson, email: e.target.value })}
              placeholder="Email (optional)"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <button onClick={handleAdd} className="px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm">
              Save
            </button>
          </div>
        </div>
      )}

      <div className="relative mb-6">
        <Search size={16} className="absolute left-3 top-2.5 text-gray-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search people..."
          className="w-full bg-gray-900 border border-gray-800 rounded-lg pl-10 pr-4 py-2 text-sm text-gray-200"
        />
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Users size={48} className="mx-auto mb-4 opacity-30" />
          <p>No people tracked yet. Mira builds this automatically from conversations.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p) => (
            <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-gray-200">{p.name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${typeColors[p.relationship_type] || typeColors.unknown}`}>
                  {p.relationship_type}
                </span>
              </div>
              {p.email && <p className="text-xs text-gray-500 mb-2">{p.email}</p>}
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
