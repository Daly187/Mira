import { useState, useEffect } from 'react'
import { getSetupStatus, saveSetupKeys, testSetupService } from '../api/client'
import { Key, Mic, Cloud, Shield, Check, X, Eye, EyeOff, Loader2, ExternalLink, AlertTriangle, MessageCircle, Cpu } from 'lucide-react'

const GROUP_META = {
  core: { label: 'Core (Required)', icon: Key, description: 'Essential keys to run Mira — API, Telegram bot, dashboard auth' },
  telegram: { label: 'Telegram Userbot', icon: MessageCircle, description: 'Autonomous messaging from your personal Telegram account' },
  local_model: { label: 'Local AI (Ollama)', icon: Cpu, description: 'Free on-device model for simple tasks — saves API costs' },
  voice: { label: 'Voice', icon: Mic, description: 'ElevenLabs for text-to-speech' },
  google: { label: 'Google APIs', icon: Cloud, description: 'Gmail and Calendar integration' },
  security: { label: 'Security', icon: Shield, description: 'Encryption and data protection' },
}

const GROUP_ORDER = ['core', 'telegram', 'local_model', 'voice', 'google', 'security']

export default function SetupPage() {
  const [status, setStatus] = useState(null)
  const [edits, setEdits] = useState({})
  const [testResults, setTestResults] = useState({})
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(null)
  const [showValues, setShowValues] = useState({})
  const [saveMessage, setSaveMessage] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStatus()
  }, [])

  async function fetchStatus() {
    try {
      const data = await getSetupStatus()
      setStatus(data)
    } catch (err) {
      console.error('Failed to fetch setup status:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (Object.keys(edits).length === 0) return
    setSaving(true)
    setSaveMessage(null)
    try {
      const data = await saveSetupKeys(edits)
      setStatus(data)
      setEdits({})
      setShowValues({})
      setSaveMessage({ type: 'success', text: 'Keys saved successfully!' })
      setTimeout(() => setSaveMessage(null), 4000)
    } catch (err) {
      setSaveMessage({ type: 'error', text: `Failed to save: ${err.message}` })
    } finally {
      setSaving(false)
    }
  }

  async function handleTest(service) {
    setTesting(service)
    setTestResults(prev => ({ ...prev, [service]: null }))
    try {
      const result = await testSetupService(service)
      setTestResults(prev => ({ ...prev, [service]: result }))
    } catch (err) {
      setTestResults(prev => ({ ...prev, [service]: { status: 'error', message: err.message } }))
    } finally {
      setTesting(null)
    }
  }

  function handleEdit(key, value) {
    setEdits(prev => ({ ...prev, [key]: value }))
  }

  function toggleShow(key) {
    setShowValues(prev => ({ ...prev, [key]: !prev[key] }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    )
  }

  if (!status) {
    return (
      <div className="text-center py-20 text-gray-400">
        <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-red-400" />
        <p>Failed to connect to Mira API. Is the backend running?</p>
        <p className="text-sm mt-2">Start with: <code className="bg-gray-800 px-2 py-1 rounded">cd agent && uvicorn api:app --port 8000</code></p>
      </div>
    )
  }

  const requiredCount = status.keys.filter(k => k.required).length
  const configuredRequired = status.keys.filter(k => k.required && k.configured).length
  const hasEdits = Object.keys(edits).length > 0

  // Group keys
  const grouped = {}
  for (const key of status.keys) {
    if (!grouped[key.group]) grouped[key.group] = []
    grouped[key.group].push(key)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Setup</h1>
        <p className="text-gray-400 mt-1">Configure API keys and connections for Mira</p>
      </div>

      {/* Progress */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-gray-400">Required Keys</span>
          <span className={`text-sm font-medium ${status.setup_complete ? 'text-green-400' : 'text-amber-400'}`}>
            {configuredRequired} of {requiredCount} configured
          </span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${status.setup_complete ? 'bg-green-500' : 'bg-purple-500'}`}
            style={{ width: `${(configuredRequired / requiredCount) * 100}%` }}
          />
        </div>
        {status.setup_complete && (
          <div className="flex items-center gap-2 mt-3 text-green-400 text-sm">
            <Check className="w-4 h-4" />
            All required keys configured — Mira is ready to run
          </div>
        )}
        {!status.setup_complete && status.missing_required.length > 0 && (
          <div className="mt-3 text-sm text-amber-400">
            Missing: {status.missing_required.map(k => {
              const schema = status.keys.find(s => s.key === k)
              return schema?.label || k
            }).join(', ')}
          </div>
        )}
      </div>

      {/* Key Groups */}
      {GROUP_ORDER.map(groupId => {
        const keys = grouped[groupId]
        if (!keys) return null
        const meta = GROUP_META[groupId]
        const Icon = meta.icon

        return (
          <div key={groupId} className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Icon className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">{meta.label}</h2>
                <p className="text-sm text-gray-500">{meta.description}</p>
              </div>
            </div>

            <div className="space-y-4">
              {keys.map(keyInfo => {
                const isEditing = keyInfo.key in edits || !keyInfo.configured
                const currentValue = edits[keyInfo.key] ?? ''
                const testResult = testResults[keyInfo.test_service]

                return (
                  <div key={keyInfo.key} className="border border-gray-800 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200">{keyInfo.label}</span>
                        {keyInfo.required && !keyInfo.configured && !(keyInfo.key in edits) && (
                          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                        )}
                        {keyInfo.configured && !(keyInfo.key in edits) && (
                          <Check className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                      {keyInfo.configured && !(keyInfo.key in edits) && (
                        <button
                          onClick={() => setEdits(prev => ({ ...prev, [keyInfo.key]: '' }))}
                          className="text-xs text-purple-400 hover:text-purple-300"
                        >
                          Change
                        </button>
                      )}
                    </div>

                    <p className="text-xs text-gray-500 mb-3">{keyInfo.help}</p>

                    {keyInfo.configured && !(keyInfo.key in edits) ? (
                      <div className="text-sm text-gray-400 font-mono bg-gray-800 rounded px-3 py-2">
                        {keyInfo.masked_value}
                      </div>
                    ) : (
                      <div className="relative">
                        <input
                          type={showValues[keyInfo.key] ? 'text' : 'password'}
                          value={currentValue}
                          onChange={(e) => handleEdit(keyInfo.key, e.target.value)}
                          placeholder={`Enter ${keyInfo.label.toLowerCase()}`}
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-purple-500 focus:outline-none pr-10"
                        />
                        <button
                          onClick={() => toggleShow(keyInfo.key)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                        >
                          {showValues[keyInfo.key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    )}

                    {/* Test Connection */}
                    {keyInfo.test_service && (keyInfo.configured || (keyInfo.key in edits && edits[keyInfo.key])) && (
                      <div className="mt-3 flex items-center gap-3">
                        <button
                          onClick={() => handleTest(keyInfo.test_service)}
                          disabled={testing === keyInfo.test_service || (keyInfo.key in edits)}
                          className="text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-1.5 rounded-lg disabled:opacity-50 flex items-center gap-1.5"
                        >
                          {testing === keyInfo.test_service ? (
                            <><Loader2 className="w-3 h-3 animate-spin" /> Testing...</>
                          ) : (
                            'Test Connection'
                          )}
                        </button>
                        {keyInfo.key in edits && (
                          <span className="text-xs text-amber-400">Save first, then test</span>
                        )}
                        {testResult && !(keyInfo.key in edits) && (
                          <span className={`text-xs flex items-center gap-1 px-2 py-1 rounded ${
                            testResult.status === 'ok'
                              ? 'bg-green-500/20 text-green-300 border border-green-500/30'
                              : 'bg-red-500/20 text-red-300 border border-red-500/30'
                          }`}>
                            {testResult.status === 'ok' ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                            {testResult.message}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}

      {/* Save Button */}
      {hasEdits && (
        <div className="sticky bottom-4 flex items-center justify-between bg-gray-900/95 backdrop-blur border border-purple-500/30 rounded-xl p-4">
          <span className="text-sm text-gray-400">
            {Object.keys(edits).length} key{Object.keys(edits).length > 1 ? 's' : ''} to save
          </span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setEdits({}); setShowValues({}) }}
              className="text-sm text-gray-400 hover:text-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
            >
              {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</> : 'Save Keys'}
            </button>
          </div>
        </div>
      )}

      {/* Save Message Toast */}
      {saveMessage && (
        <div className={`fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm flex items-center gap-2 shadow-lg z-50 ${
          saveMessage.type === 'success'
            ? 'bg-green-500/20 text-green-300 border border-green-500/30'
            : 'bg-red-500/20 text-red-300 border border-red-500/30'
        }`}>
          {saveMessage.type === 'success' ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
          {saveMessage.text}
        </div>
      )}

      {/* Help Links */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Quick Links</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Anthropic Console', url: 'https://console.anthropic.com' },
            { label: 'Telegram BotFather', url: 'https://t.me/BotFather' },
            { label: 'Telegram API Keys', url: 'https://my.telegram.org' },
            { label: 'Ollama Download', url: 'https://ollama.com/download' },
            { label: 'ElevenLabs', url: 'https://elevenlabs.io' },
            { label: 'Google Cloud Console', url: 'https://console.cloud.google.com' },
          ].map(link => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-purple-400 hover:text-purple-300 bg-gray-800 rounded-lg px-3 py-2"
            >
              <ExternalLink className="w-3 h-3" />
              {link.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
