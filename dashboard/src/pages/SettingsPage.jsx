import { useState, useEffect } from 'react'
import { Settings, Shield, TrendingUp, Clock, Brain, Zap, Wifi, WifiOff } from 'lucide-react'
import { getSettings, getSettingsSchema, updateSetting, getModules, getBackendUrl, setBackendUrl } from '../api/client'

const sectionIcons = {
  trading: TrendingUp,
  briefing: Clock,
  autonomy: Shield,
  models: Brain,
  polymarket: Zap,
}

const sectionLabels = {
  trading: 'Trading Risk Limits',
  briefing: 'Daily Briefing',
  autonomy: 'Autonomy Rules',
  models: 'AI Models',
  polymarket: 'Polymarket',
}

export default function SettingsPage() {
  const [schema, setSchema] = useState(null)
  const [settings, setSettings] = useState(null)
  const [modules, setModules] = useState(null)
  const [saving, setSaving] = useState('')
  const [backendError, setBackendError] = useState(false)
  const [backendUrl, setBackendUrlState] = useState(getBackendUrl() || '')
  const [urlSaving, setUrlSaving] = useState(false)

  useEffect(() => {
    if (!getBackendUrl()) {
      setBackendError(true)
      return
    }
    Promise.all([getSettingsSchema(), getSettings(), getModules()])
      .then(([s, v, m]) => { setSchema(s); setSettings(v); setModules(m) })
      .catch((e) => {
        console.error('Failed to load settings:', e)
        setBackendError(true)
      })
  }, [])

  async function handleChange(key, value) {
    setSaving(key)
    try {
      await updateSetting(key, value)
      setSettings(prev => {
        const updated = { ...prev }
        for (const group of Object.keys(updated)) {
          if (key in (schema[group] || {})) {
            updated[group] = { ...updated[group], [key]: value }
          }
        }
        return updated
      })
    } catch (e) {
      console.error('Failed to save:', e)
    }
    setSaving('')
  }

  const handleBackendSave = async () => {
    setUrlSaving(true)
    const cleanUrl = backendUrl.trim().replace(/\/+$/, '')
    try {
      const res = await fetch(`${cleanUrl}/api/health`)
      if (!res.ok) throw new Error('Bad response')
      const data = await res.json()
      if (data.status !== 'ok') throw new Error('Invalid backend')
      setBackendUrl(cleanUrl)
      setBackendUrlState(cleanUrl)
      setBackendError(false)
      // Reload settings
      const [s, v, m] = await Promise.all([getSettingsSchema(), getSettings(), getModules()])
      setSchema(s); setSettings(v); setModules(m)
    } catch (e) {
      alert('Cannot connect to backend: ' + e.message)
    }
    setUrlSaving(false)
  }

  if (backendError || (!schema && !settings)) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-2">Settings</h1>
        <p className="text-gray-500 text-sm mb-8">Configure Mira's behaviour, risk limits, and autonomy rules</p>

        <div className="bg-gray-900 border border-yellow-500/30 rounded-xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <WifiOff size={24} className="text-yellow-400" />
            <h2 className="text-lg font-semibold text-yellow-400">Backend Not Connected</h2>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            Enter the URL where your Mira agent is running to load settings.
          </p>
          <div className="flex gap-3">
            <input
              type="url"
              value={backendUrl}
              onChange={(e) => setBackendUrlState(e.target.value)}
              placeholder="http://100.x.x.x:8000"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-600 text-sm"
            />
            <button
              onClick={handleBackendSave}
              disabled={urlSaving || !backendUrl.trim()}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg text-sm"
            >
              {urlSaving ? 'Testing...' : 'Connect'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!schema || !settings) return <p className="text-gray-500">Loading settings...</p>

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Settings</h1>
      <p className="text-gray-500 text-sm mb-8">Configure Mira's behaviour, risk limits, and autonomy rules</p>

      <div className="space-y-8">
        {Object.entries(schema).map(([group, fields]) => {
          const Icon = sectionIcons[group] || Settings
          return (
            <div key={group} className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Icon size={20} className="text-mira-400" />
                {sectionLabels[group] || group}
              </h2>
              <div className="space-y-4">
                {Object.entries(fields).map(([key, fieldSchema]) => {
                  const currentValue = settings[group]?.[key] ?? fieldSchema.default
                  return (
                    <div key={key} className="flex items-center justify-between py-2">
                      <div>
                        <label className="text-sm text-gray-300">{fieldSchema.label}</label>
                        <p className="text-xs text-gray-600">
                          {key} {saving === key && '(saving...)'}
                        </p>
                      </div>
                      <div className="w-64">
                        {fieldSchema.options ? (
                          <select
                            value={currentValue}
                            onChange={(e) => handleChange(key, e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                          >
                            {fieldSchema.options.map(opt => (
                              <option key={opt} value={opt}>{opt.replace(/_/g, ' ')}</option>
                            ))}
                          </select>
                        ) : fieldSchema.type === 'bool' ? (
                          <button
                            onClick={() => handleChange(key, !currentValue)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition w-full ${
                              currentValue
                                ? 'bg-green-600/20 text-green-400 border border-green-700'
                                : 'bg-gray-800 text-gray-500 border border-gray-700'
                            }`}
                          >
                            {currentValue ? 'Enabled' : 'Disabled'}
                          </button>
                        ) : (
                          <input
                            type={fieldSchema.type === 'float' ? 'number' : 'text'}
                            step={fieldSchema.type === 'float' ? '0.1' : undefined}
                            value={currentValue}
                            onChange={(e) => handleChange(key, e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
                          />
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Backend Connection */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Wifi size={20} className="text-green-400" /> Backend Connection
        </h2>
        <div className="flex items-center gap-3">
          <input
            type="url"
            value={backendUrl}
            onChange={(e) => setBackendUrlState(e.target.value)}
            placeholder="http://100.x.x.x:8000"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
          />
          <button
            onClick={handleBackendSave}
            disabled={urlSaving}
            className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm"
          >
            {urlSaving ? 'Testing...' : 'Update'}
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-2">
          Current: {getBackendUrl() || 'Not configured (using same-origin)'}
        </p>
      </div>

      {/* Module Status */}
      {modules && (
        <div className="mt-8 bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap size={20} className="text-yellow-400" /> Module Status
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(modules).map(([name, info]) => {
              if (typeof info === 'object' && info.status) {
                return (
                  <div key={name} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                    <span className="text-sm text-gray-300">{name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">Phase {info.phase}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        info.status === 'active'
                          ? 'bg-green-500/20 text-green-300'
                          : 'bg-gray-500/20 text-gray-400'
                      }`}>
                        {info.status}
                      </span>
                    </div>
                  </div>
                )
              }
              return null
            })}
          </div>
        </div>
      )}
    </div>
  )
}
