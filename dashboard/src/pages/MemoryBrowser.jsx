import { useState, useEffect } from 'react'
import { Brain, Search, Plus, Tag } from 'lucide-react'
import { getMemories, createMemory } from '../api/client'

export default function MemoryBrowser() {
  const [memories, setMemories] = useState([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [minImportance, setMinImportance] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newMemory, setNewMemory] = useState({ content: '', category: 'general', importance: 3 })
  const [loading, setLoading] = useState(true)

  const categories = ['general', 'personal', 'work', 'trading', 'health', 'social', 'learning']

  async function load() {
    setLoading(true)
    try {
      const params = {}
      if (search) params.query = search
      if (category) params.category = category
      if (minImportance) params.min_importance = minImportance
      const data = await getMemories(params)
      setMemories(data)
    } catch (e) {
      console.error('Failed to load memories:', e)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [category, minImportance])

  async function handleSearch(e) {
    e.preventDefault()
    await load()
  }

  async function handleAdd() {
    try {
      await createMemory(newMemory)
      setNewMemory({ content: '', category: 'general', importance: 3 })
      setShowAdd(false)
      await load()
    } catch (e) {
      console.error('Failed to create memory:', e)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Second Brain</h1>
          <p className="text-gray-500 text-sm mt-1">Browse and search Mira's memory</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm transition"
        >
          <Plus size={16} /> Add Memory
        </button>
      </div>

      {/* Add memory form */}
      {showAdd && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <textarea
            value={newMemory.content}
            onChange={(e) => setNewMemory({ ...newMemory, content: e.target.value })}
            placeholder="What do you want Mira to remember?"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 mb-3"
            rows={3}
          />
          <div className="flex items-center gap-3">
            <select
              value={newMemory.category}
              onChange={(e) => setNewMemory({ ...newMemory, category: e.target.value })}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            >
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select
              value={newMemory.importance}
              onChange={(e) => setNewMemory({ ...newMemory, importance: parseInt(e.target.value) })}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            >
              {[1,2,3,4,5].map(i => <option key={i} value={i}>Importance: {i}</option>)}
            </select>
            <button onClick={handleAdd} className="px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm">
              Save
            </button>
          </div>
        </div>
      )}

      {/* Search and filters */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <form onSubmit={handleSearch} className="flex items-center gap-3">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-2.5 text-gray-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search memories by keyword..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-sm text-gray-200"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
          >
            <option value="">All categories</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select
            value={minImportance}
            onChange={(e) => setMinImportance(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
          >
            <option value="">Any importance</option>
            {[3,4,5].map(i => <option key={i} value={i}>{i}+ importance</option>)}
          </select>
          <button type="submit" className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">
            Search
          </button>
        </form>
      </div>

      {/* Memory list */}
      <div className="space-y-3">
        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : memories.length === 0 ? (
          <div className="text-center py-12 text-gray-600">
            <Brain size={48} className="mx-auto mb-4 opacity-30" />
            <p>No memories found. Start talking to Mira to build her second brain.</p>
          </div>
        ) : (
          memories.map((m) => (
            <div key={m.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 bg-mira-500/20 text-mira-300 rounded-full">{m.category}</span>
                  <span className="text-xs text-gray-600">importance: {m.importance}/5</span>
                  <span className="text-xs text-gray-600">source: {m.source}</span>
                </div>
                <span className="text-xs text-gray-600">{m.created_at}</span>
              </div>
              <p className="text-sm text-gray-300">{m.content}</p>
              {m.tags && m.tags !== '[]' && (
                <div className="flex items-center gap-1 mt-2">
                  <Tag size={12} className="text-gray-600" />
                  <span className="text-xs text-gray-600">{m.tags}</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
