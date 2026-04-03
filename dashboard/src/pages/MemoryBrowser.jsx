import { useState, useEffect } from 'react'
import { Brain, Search, Plus, Tag, Trash2, Pencil, Check, X } from 'lucide-react'
import { getMemories, createMemory, deleteMemory, updateMemory } from '../api/client'

export default function MemoryBrowser() {
  const [memories, setMemories] = useState([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [minImportance, setMinImportance] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newMemory, setNewMemory] = useState({ content: '', category: 'general', importance: 3 })
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editData, setEditData] = useState({})

  const categories = ['general', 'personal', 'work', 'trading', 'health', 'social', 'learning']

  function showToast(message) {
    setToast(message)
    setTimeout(() => setToast(null), 2500)
  }

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
    if (!newMemory.content.trim()) return
    try {
      await createMemory(newMemory)
      setNewMemory({ content: '', category: 'general', importance: 3 })
      setShowAdd(false)
      showToast('Memory saved successfully')
      await load()
    } catch (e) {
      console.error('Failed to create memory:', e)
    }
  }

  async function handleDelete(memory) {
    if (!confirm('Delete this memory? This cannot be undone.')) return
    try {
      await deleteMemory(memory.id)
      showToast('Memory deleted')
      await load()
    } catch (e) {
      console.error('Failed to delete memory:', e)
    }
  }

  function startEdit(memory) {
    setEditingId(memory.id)
    setEditData({
      content: memory.content,
      category: memory.category,
      importance: memory.importance,
    })
  }

  async function saveEdit() {
    try {
      await updateMemory(editingId, editData)
      setEditingId(null)
      showToast('Memory updated')
      await load()
    } catch (e) {
      console.error('Failed to update memory:', e)
    }
  }

  function cancelEdit() {
    setEditingId(null)
    setEditData({})
  }

  return (
    <div>
      {/* Toast notification */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-mira-500 text-white px-4 py-2 rounded-lg text-sm shadow-lg animate-fade-in">
          {toast}
        </div>
      )}

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
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 text-gray-400 hover:text-gray-200 text-sm"
            >
              Cancel
            </button>
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
            {[1,2,3,4,5].map(i => <option key={i} value={i}>{i}+ importance</option>)}
          </select>
          <button type="submit" className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">
            Search
          </button>
        </form>
      </div>

      {/* Results count */}
      {!loading && (
        <p className="text-xs text-gray-600 mb-3">{memories.length} memor{memories.length === 1 ? 'y' : 'ies'} found</p>
      )}

      {/* Memory list */}
      <div className="space-y-3">
        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : memories.length === 0 ? (
          <div className="text-center py-12 text-gray-600">
            <Brain size={48} className="mx-auto mb-4 opacity-30" />
            <p>{search || category || minImportance
              ? 'No memories match your search. Try adjusting your filters.'
              : 'No memories found. Start talking to Mira to build her second brain.'}</p>
          </div>
        ) : (
          memories.map((m) => (
            <div key={m.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition group">
              {editingId === m.id ? (
                /* Inline edit mode */
                <div>
                  <textarea
                    value={editData.content}
                    onChange={(e) => setEditData({ ...editData, content: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-sm text-gray-200 mb-2"
                    rows={3}
                  />
                  <div className="flex items-center gap-2">
                    <select
                      value={editData.category}
                      onChange={(e) => setEditData({ ...editData, category: e.target.value })}
                      className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-300"
                    >
                      {categories.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <select
                      value={editData.importance}
                      onChange={(e) => setEditData({ ...editData, importance: parseInt(e.target.value) })}
                      className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-300"
                    >
                      {[1,2,3,4,5].map(i => <option key={i} value={i}>{i}/5</option>)}
                    </select>
                    <button onClick={saveEdit} className="text-green-400 hover:text-green-300" title="Save">
                      <Check size={16} />
                    </button>
                    <button onClick={cancelEdit} className="text-gray-500 hover:text-gray-300" title="Cancel">
                      <X size={16} />
                    </button>
                  </div>
                </div>
              ) : (
                /* Normal display mode */
                <>
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 bg-mira-500/20 text-mira-300 rounded-full">{m.category}</span>
                      <span className="text-xs text-gray-600">importance: {m.importance}/5</span>
                      <span className="text-xs text-gray-600">source: {m.source}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-600">{m.created_at}</span>
                      <button
                        onClick={() => startEdit(m)}
                        className="opacity-0 group-hover:opacity-100 transition text-gray-600 hover:text-mira-400"
                        title="Edit memory"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(m)}
                        className="opacity-0 group-hover:opacity-100 transition text-gray-600 hover:text-red-400"
                        title="Delete memory"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <p className="text-sm text-gray-300">{m.content}</p>
                  {m.tags && m.tags !== '[]' && (
                    <div className="flex items-center gap-1 mt-2">
                      <Tag size={12} className="text-gray-600" />
                      <span className="text-xs text-gray-600">{m.tags}</span>
                    </div>
                  )}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
