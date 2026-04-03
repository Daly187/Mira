import { useState, useEffect, useRef } from 'react'
import {
  Ghost, Users, MessageCircle, Plus, Trash2, Save, Eye, Send,
  ShieldAlert, UserPlus, ChevronDown, ChevronRight, Settings2,
  Smile, MessageSquare, AlertTriangle, Clock, Calendar, RefreshCw, X
} from 'lucide-react'
import {
  getSoulSettings, upsertSoulSetting, deleteSoulSetting,
  getTelegramContacts, upsertTelegramContact, deleteTelegramContact,
  getContactMessages, getPendingReviews,
  sendTelegramMessage, getUnreadCounts, getScheduledMessages,
  cancelScheduledMessage, triggerTelegramSync,
} from '../api/client'

const AUTONOMY_LEVELS = [
  { value: 'auto_reply', label: 'Auto Reply', color: 'text-green-400', desc: 'Mira replies instantly without your approval' },
  { value: 'review_first', label: 'Review First', color: 'text-yellow-400', desc: 'Mira drafts a reply and waits for your approval' },
  { value: 'silent', label: 'Silent', color: 'text-gray-400', desc: 'Mira reads but never replies' },
]

const TONES = ['casual', 'warm', 'professional', 'formal', 'blunt', 'playful']
const EMOJI_OPTIONS = ['none', 'minimal', 'moderate', 'heavy']
const RESPONSE_LENGTHS = ['short', 'medium', 'detailed']

export default function SoulPage() {
  const [tab, setTab] = useState('soul')
  const [soulSettings, setSoulSettings] = useState([])
  const [contacts, setContacts] = useState([])
  const [reviews, setReviews] = useState([])
  const [scheduled, setScheduled] = useState([])
  const [unreadCounts, setUnreadCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const [editingSoul, setEditingSoul] = useState(null)
  const [newRelType, setNewRelType] = useState('')

  const [showAddContact, setShowAddContact] = useState(false)
  const [contactForm, setContactForm] = useState({
    name: '', telegram_user_id: '', telegram_username: '',
    autonomy_level: 'review_first', relationship_type: 'friend',
    communication_style: 'casual and friendly',
  })

  const [selectedContact, setSelectedContact] = useState(null)
  const [messages, setMessages] = useState([])

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [s, c, r] = await Promise.all([
        getSoulSettings(), getTelegramContacts(), getPendingReviews(),
      ])
      setSoulSettings(s || [])
      setContacts(c || [])
      setReviews(r || [])

      // Load unread counts (non-blocking)
      getUnreadCounts().then(counts => {
        const map = {}
        for (const c of (counts || [])) map[c.contact_id] = c.unread_count
        setUnreadCounts(map)
      }).catch(() => {})

      // Load scheduled messages (non-blocking)
      getScheduledMessages().then(s => setScheduled(s || [])).catch(() => {})
    } catch (e) {
      console.error('Failed to load soul data:', e)
    }
    setLoading(false)
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      await triggerTelegramSync()
      await loadData()
      if (selectedContact) loadHistory(selectedContact)
    } catch (e) {
      console.error('Sync failed:', e)
    }
    setSyncing(false)
  }

  // ── Soul Settings Handlers ─────────────────────────────

  const handleSaveSoul = async (setting) => {
    setSaving(true)
    try {
      await upsertSoulSetting({
        ...setting,
        escalation_keywords: typeof setting.escalation_keywords === 'string'
          ? JSON.parse(setting.escalation_keywords || '[]')
          : setting.escalation_keywords,
      })
      await loadData()
      setEditingSoul(null)
    } catch (e) { console.error('Failed to save soul setting:', e) }
    setSaving(false)
  }

  const handleDeleteSoul = async (relType) => {
    if (!confirm(`Delete soul settings for "${relType}"?`)) return
    try { await deleteSoulSetting(relType); await loadData() }
    catch (e) { console.error('Failed to delete soul setting:', e) }
  }

  const handleAddSoulType = async () => {
    if (!newRelType.trim()) return
    await upsertSoulSetting({ relationship_type: newRelType.trim().toLowerCase() })
    setNewRelType('')
    await loadData()
  }

  // ── Contact Handlers ───────────────────────────────────

  const handleSaveContact = async () => {
    if (!contactForm.name.trim()) return
    setSaving(true)
    try {
      await upsertTelegramContact(contactForm)
      setShowAddContact(false)
      setContactForm({
        name: '', telegram_user_id: '', telegram_username: '',
        autonomy_level: 'review_first', relationship_type: 'friend',
        communication_style: 'casual and friendly',
      })
      await loadData()
    } catch (e) { console.error('Failed to save contact:', e) }
    setSaving(false)
  }

  const handleDeleteContact = async (id, name) => {
    if (!confirm(`Remove "${name}" from Mira's contact list?`)) return
    try { await deleteTelegramContact(id); await loadData() }
    catch (e) { console.error('Failed to delete contact:', e) }
  }

  const handleUpdateContact = async (contact, updates) => {
    try { await upsertTelegramContact({ name: contact.name, ...updates }); await loadData() }
    catch (e) { console.error('Failed to update contact:', e) }
  }

  // ── History ────────────────────────────────────────────

  const loadHistory = async (contact) => {
    setSelectedContact(contact)
    try {
      const msgs = await getContactMessages(contact.id)
      setMessages(msgs || [])
    } catch (e) {
      console.error('Failed to load messages:', e)
      setMessages([])
    }
  }

  const handleCancelScheduled = async (id) => {
    try { await cancelScheduledMessage(id); await loadData() }
    catch (e) { console.error('Cancel failed:', e) }
  }

  const pendingScheduled = scheduled.filter(s => s.status === 'pending')
  const totalUnread = Object.values(unreadCounts).reduce((a, b) => a + b, 0)

  if (loading) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-2">Soul</h1>
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold">Soul</h1>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-gray-500 hover:text-mira-400 transition flex items-center gap-2 text-sm"
          title="Sync conversations from Telegram"
        >
          <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Syncing...' : 'Sync'}
        </button>
      </div>
      <p className="text-gray-500 text-sm mb-8">
        Control how Mira communicates on your behalf — per relationship type and per contact
      </p>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'soul', icon: Ghost, label: 'Communication Rules' },
          { id: 'contacts', icon: Users, label: `Contacts (${contacts.length})`, badge: totalUnread },
          { id: 'reviews', icon: ShieldAlert, label: `Reviews (${reviews.length})` },
          { id: 'history', icon: MessageCircle, label: 'History' },
          { id: 'scheduled', icon: Calendar, label: `Scheduled (${pendingScheduled.length})` },
        ].map(({ id, icon: Icon, label, badge }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition relative ${
              tab === id
                ? 'bg-mira-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}
          >
            <Icon size={14} />
            {label}
            {badge > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Soul Settings Tab */}
      {tab === 'soul' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 mb-4">
            <input
              type="text"
              value={newRelType}
              onChange={(e) => setNewRelType(e.target.value)}
              placeholder="Add relationship type (e.g. mentor, partner)"
              className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-600 text-sm flex-1"
              onKeyDown={(e) => e.key === 'Enter' && handleAddSoulType()}
            />
            <button onClick={handleAddSoulType}
              className="bg-mira-500 hover:bg-mira-600 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <Plus size={14} /> Add Type
            </button>
          </div>
          {soulSettings.map((setting) => (
            <SoulCard key={setting.relationship_type} setting={setting}
              isEditing={editingSoul === setting.relationship_type}
              onEdit={() => setEditingSoul(editingSoul === setting.relationship_type ? null : setting.relationship_type)}
              onSave={handleSaveSoul} onDelete={() => handleDeleteSoul(setting.relationship_type)} saving={saving} />
          ))}
          {soulSettings.length === 0 && (
            <div className="text-center py-12 text-gray-600">
              <Ghost size={48} className="mx-auto mb-4 opacity-30" />
              <p>No soul settings configured yet.</p>
              <p className="text-sm mt-2">Add a relationship type above to get started.</p>
            </div>
          )}
        </div>
      )}

      {/* Contacts Tab */}
      {tab === 'contacts' && (
        <div>
          <button onClick={() => setShowAddContact(!showAddContact)}
            className="bg-mira-500 hover:bg-mira-600 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2 mb-4">
            <UserPlus size={14} /> Add Contact
          </button>

          {showAddContact && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-4">
              <h3 className="text-sm font-semibold text-gray-300 mb-4">New Telegram Contact</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Name *</label>
                  <input type="text" value={contactForm.name}
                    onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                    placeholder="Contact name"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">@username (for userbot)</label>
                  <input type="text" value={contactForm.telegram_username}
                    onChange={(e) => setContactForm({ ...contactForm, telegram_username: e.target.value })}
                    placeholder="@username"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Telegram User ID (for bot)</label>
                  <input type="text" value={contactForm.telegram_user_id}
                    onChange={(e) => setContactForm({ ...contactForm, telegram_user_id: e.target.value })}
                    placeholder="e.g. 123456789"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Autonomy Level</label>
                  <select value={contactForm.autonomy_level}
                    onChange={(e) => setContactForm({ ...contactForm, autonomy_level: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm">
                    {AUTONOMY_LEVELS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Relationship Type</label>
                  <select value={contactForm.relationship_type}
                    onChange={(e) => setContactForm({ ...contactForm, relationship_type: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm">
                    {soulSettings.map((s) => <option key={s.relationship_type} value={s.relationship_type}>{s.relationship_type}</option>)}
                    <option value="unknown">unknown</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Communication Style</label>
                  <input type="text" value={contactForm.communication_style}
                    onChange={(e) => setContactForm({ ...contactForm, communication_style: e.target.value })}
                    placeholder="e.g. casual, direct, sometimes banter"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <button onClick={handleSaveContact} disabled={saving || !contactForm.name.trim()}
                  className="bg-mira-500 hover:bg-mira-600 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm">
                  {saving ? 'Saving...' : 'Add Contact'}
                </button>
                <button onClick={() => setShowAddContact(false)}
                  className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-4 py-2 rounded-lg text-sm">Cancel</button>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {contacts.map((contact) => (
              <ContactCard key={contact.id} contact={contact} soulSettings={soulSettings}
                unreadCount={unreadCounts[contact.id] || 0}
                onUpdate={(updates) => handleUpdateContact(contact, updates)}
                onDelete={() => handleDeleteContact(contact.id, contact.name)}
                onViewHistory={() => { loadHistory(contact); setTab('history') }} />
            ))}
            {contacts.length === 0 && (
              <div className="text-center py-12 text-gray-600">
                <Users size={48} className="mx-auto mb-4 opacity-30" />
                <p>No contacts added yet.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reviews Tab */}
      {tab === 'reviews' && (
        <div className="space-y-4">
          {reviews.length === 0 ? (
            <div className="text-center py-12 text-gray-600">
              <ShieldAlert size={48} className="mx-auto mb-4 opacity-30" />
              <p>No pending reviews.</p>
              <p className="text-sm mt-2">Messages from review-first contacts will appear here.</p>
            </div>
          ) : reviews.map((msg) => (
            <div key={msg.id} className="bg-gray-900 border border-yellow-500/30 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-200">{msg.contact_name}</span>
                <span className="text-xs text-gray-500">{new Date(msg.created_at).toLocaleString()}</span>
              </div>
              <div className="bg-gray-800 rounded-lg p-3 mb-2 text-sm text-gray-300">{msg.content}</div>
              <span className="text-xs text-yellow-400">Pending approval in Telegram</span>
            </div>
          ))}
        </div>
      )}

      {/* History Tab — with message composer */}
      {tab === 'history' && (
        <div className="flex gap-4">
          <div className="w-48 space-y-1">
            {contacts.map((c) => (
              <button key={c.id} onClick={() => loadHistory(c)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition relative ${
                  selectedContact?.id === c.id
                    ? 'bg-mira-500/20 text-mira-400 border border-mira-500/30'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                }`}>
                <div className="font-medium truncate">{c.name}</div>
                <div className="text-xs text-gray-600">{c.conversation_count || 0} msgs</div>
                {unreadCounts[c.id] > 0 && (
                  <span className="absolute top-1 right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                    {unreadCounts[c.id]}
                  </span>
                )}
              </button>
            ))}
            {contacts.length === 0 && <p className="text-xs text-gray-600 px-3">No contacts</p>}
          </div>

          <div className="flex-1 bg-gray-900 border border-gray-800 rounded-xl flex flex-col min-h-[500px]">
            {selectedContact ? (
              <>
                <div className="px-4 py-3 border-b border-gray-800">
                  <h3 className="font-semibold text-gray-200">
                    {selectedContact.name}
                    <span className="text-xs text-gray-500 ml-2">{selectedContact.relationship_type}</span>
                    {selectedContact.telegram_username && (
                      <span className="text-xs text-gray-600 ml-2">@{selectedContact.telegram_username}</span>
                    )}
                  </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {messages.length === 0 ? (
                    <p className="text-gray-600 text-sm">No messages yet. Send the first message below.</p>
                  ) : messages.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.role === 'assistant' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[75%] rounded-xl px-4 py-2 text-sm ${
                        msg.role === 'assistant'
                          ? 'bg-mira-500/20 text-mira-300 border border-mira-500/30'
                          : 'bg-gray-800 text-gray-300'
                      }`}>
                        <p>{msg.content}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-gray-600">
                            {new Date(msg.created_at).toLocaleTimeString()}
                          </span>
                          {msg.source === 'userbot' && (
                            <span className="text-xs text-blue-400/60">via userbot</span>
                          )}
                          {msg.flagged_for_review === 1 && (
                            <span className="text-xs text-yellow-400">
                              {msg.review_status === 'none' ? 'Pending review' : msg.review_status}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                {/* Message Composer */}
                <MessageComposer contactId={selectedContact.id} onSent={() => loadHistory(selectedContact)} />
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-600">
                <p>Select a contact to view conversation history</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Scheduled Tab */}
      {tab === 'scheduled' && (
        <div className="space-y-4">
          {scheduled.length === 0 ? (
            <div className="text-center py-12 text-gray-600">
              <Calendar size={48} className="mx-auto mb-4 opacity-30" />
              <p>No scheduled messages.</p>
              <p className="text-sm mt-2">Schedule messages from the History tab using the clock icon.</p>
            </div>
          ) : scheduled.map((msg) => (
            <div key={msg.id} className={`bg-gray-900 border rounded-xl p-4 ${
              msg.status === 'pending' ? 'border-yellow-500/30' :
              msg.status === 'sent' ? 'border-green-500/30' :
              msg.status === 'failed' ? 'border-red-500/30' : 'border-gray-800'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-semibold text-gray-200">{msg.contact_name}</span>
                  {msg.reason && <span className="text-xs text-gray-500 ml-2">({msg.reason})</span>}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    msg.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                    msg.status === 'sent' ? 'bg-green-500/20 text-green-400' :
                    msg.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                    'bg-gray-700 text-gray-400'
                  }`}>{msg.status}</span>
                  {msg.status === 'pending' && (
                    <button onClick={() => handleCancelScheduled(msg.id)}
                      className="text-gray-500 hover:text-red-400 transition" title="Cancel">
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
              <div className="bg-gray-800 rounded-lg p-3 text-sm text-gray-300 mb-2">{msg.content}</div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <Clock size={10} /> Send at: {new Date(msg.send_at).toLocaleString()}
                </span>
                {msg.sent_at && <span>Sent: {new Date(msg.sent_at).toLocaleString()}</span>}
                {msg.error && <span className="text-red-400">Error: {msg.error}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Message Composer ────────────────────────────────────

function MessageComposer({ contactId, onSent }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [showSchedule, setShowSchedule] = useState(false)
  const [scheduleAt, setScheduleAt] = useState('')
  const inputRef = useRef(null)

  const handleSend = async () => {
    if (!text.trim()) return
    setSending(true)
    try {
      await sendTelegramMessage(contactId, text.trim(), showSchedule ? scheduleAt : null)
      setText('')
      setShowSchedule(false)
      setScheduleAt('')
      onSent()
    } catch (e) {
      console.error('Send failed:', e)
      alert('Failed to send: ' + e.message)
    }
    setSending(false)
  }

  return (
    <div className="border-t border-gray-800 p-3">
      {showSchedule && (
        <div className="flex items-center gap-2 mb-2">
          <Clock size={14} className="text-yellow-400" />
          <input type="datetime-local" value={scheduleAt}
            onChange={(e) => setScheduleAt(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1 text-white text-sm flex-1" />
          <button onClick={() => { setShowSchedule(false); setScheduleAt('') }}
            className="text-gray-500 hover:text-gray-300"><X size={14} /></button>
        </div>
      )}
      <div className="flex items-center gap-2">
        <button onClick={() => setShowSchedule(!showSchedule)}
          className={`p-2 rounded-lg transition ${showSchedule ? 'text-yellow-400 bg-yellow-500/10' : 'text-gray-500 hover:text-gray-300'}`}
          title="Schedule message">
          <Clock size={16} />
        </button>
        <input ref={inputRef} type="text" value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Type a message..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-mira-500" />
        <button onClick={handleSend} disabled={sending || !text.trim() || (showSchedule && !scheduleAt)}
          className="bg-mira-500 hover:bg-mira-600 disabled:bg-gray-700 disabled:text-gray-500 text-white p-2 rounded-lg transition">
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}

// ── Soul Card Component ──────────────────────────────────

function SoulCard({ setting, isEditing, onEdit, onSave, onDelete, saving }) {
  const [form, setForm] = useState(setting)
  useEffect(() => { setForm(setting) }, [setting])
  const handleChange = (field, value) => setForm({ ...form, [field]: value })

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-gray-800/50" onClick={onEdit}>
        <div className="flex items-center gap-3">
          {isEditing ? <ChevronDown size={16} className="text-gray-500" /> : <ChevronRight size={16} className="text-gray-500" />}
          <Settings2 size={16} className="text-mira-400" />
          <h3 className="font-semibold text-gray-200 capitalize">{setting.relationship_type}</h3>
          {!setting.enabled && <span className="text-xs bg-gray-700 text-gray-500 px-2 py-0.5 rounded">Disabled</span>}
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>Tone: {setting.tone}</span>
          <span>Formality: {setting.formality}/5</span>
          <span>Length: {setting.response_length}</span>
          {setting.proactive_outreach ? <span className="text-green-400">Proactive</span> : null}
        </div>
      </div>

      {isEditing && (
        <div className="px-5 pb-5 border-t border-gray-800 pt-4">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tone</label>
              <select value={form.tone} onChange={(e) => handleChange('tone', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm">
                {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Formality (1-5)</label>
              <input type="range" min="1" max="5" value={form.formality}
                onChange={(e) => handleChange('formality', parseInt(e.target.value))} className="w-full accent-purple-500" />
              <div className="flex justify-between text-xs text-gray-600"><span>Very casual</span><span>Very formal</span></div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Humor Level (1-5)</label>
              <input type="range" min="1" max="5" value={form.humor_level}
                onChange={(e) => handleChange('humor_level', parseInt(e.target.value))} className="w-full accent-purple-500" />
              <div className="flex justify-between text-xs text-gray-600"><span>Serious</span><span>Very funny</span></div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Emoji Usage</label>
              <select value={form.emoji_usage} onChange={(e) => handleChange('emoji_usage', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm">
                {EMOJI_OPTIONS.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Response Length</label>
              <select value={form.response_length} onChange={(e) => handleChange('response_length', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm">
                {RESPONSE_LENGTHS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Proactive Outreach</label>
              <button onClick={() => handleChange('proactive_outreach', form.proactive_outreach ? 0 : 1)}
                className={`px-4 py-2 rounded-lg text-sm w-full ${form.proactive_outreach
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : 'bg-gray-800 text-gray-500 border border-gray-700'}`}>
                {form.proactive_outreach ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          </div>
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">Escalation Keywords (comma-separated)</label>
            <input type="text"
              value={typeof form.escalation_keywords === 'string'
                ? (() => { try { return JSON.parse(form.escalation_keywords).join(', ') } catch { return form.escalation_keywords } })()
                : (form.escalation_keywords || []).join(', ')}
              onChange={(e) => handleChange('escalation_keywords',
                JSON.stringify(e.target.value.split(',').map(k => k.trim()).filter(Boolean)))}
              placeholder="urgent, payment, deadline"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">Custom Instructions</label>
            <textarea value={form.custom_instructions || ''}
              onChange={(e) => handleChange('custom_instructions', e.target.value)}
              placeholder="Additional rules for how Mira should communicate with this type of contact..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm h-20 resize-y" />
          </div>
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <button onClick={() => onSave(form)} disabled={saving}
                className="bg-mira-500 hover:bg-mira-600 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2">
                <Save size={14} /> {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => handleChange('enabled', form.enabled ? 0 : 1)}
                className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-4 py-2 rounded-lg text-sm">
                {form.enabled ? 'Disable' : 'Enable'}
              </button>
            </div>
            <button onClick={onDelete} className="text-red-400 hover:text-red-300 text-sm flex items-center gap-1">
              <Trash2 size={14} /> Delete
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Contact Card Component ───────────────────────────────

function ContactCard({ contact, soulSettings, unreadCount, onUpdate, onDelete, onViewHistory }) {
  const autonomy = AUTONOMY_LEVELS.find(a => a.value === contact.autonomy_level) || AUTONOMY_LEVELS[1]

  const daysSince = (dateStr) => {
    if (!dateStr) return null
    return Math.floor((new Date() - new Date(dateStr)) / 86400000)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-200">{contact.name}</h3>
            {unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5">{unreadCount} new</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            <span className="capitalize">{contact.relationship_type}</span>
            {contact.telegram_username && <span>@{contact.telegram_username}</span>}
            {contact.telegram_user_id && <span>ID: {contact.telegram_user_id}</span>}
            {contact.last_message_at && (
              <span className="flex items-center gap-1"><Clock size={10} />{daysSince(contact.last_message_at)}d ago</span>
            )}
            <span>{contact.conversation_count || 0} messages</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select value={contact.autonomy_level}
            onChange={(e) => onUpdate({ autonomy_level: e.target.value })}
            className={`bg-gray-800 border border-gray-700 rounded-lg px-3 py-1 text-sm ${autonomy.color}`}>
            {AUTONOMY_LEVELS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
          <button onClick={onViewHistory} className="text-gray-500 hover:text-gray-300 transition" title="View history">
            <Eye size={16} />
          </button>
          <button onClick={onDelete} className="text-gray-500 hover:text-red-400 transition" title="Remove contact">
            <Trash2 size={16} />
          </button>
        </div>
      </div>
      {contact.communication_style && contact.communication_style !== 'casual and friendly' && (
        <p className="text-xs text-gray-600 mt-2 italic">Style: {contact.communication_style}</p>
      )}
    </div>
  )
}
