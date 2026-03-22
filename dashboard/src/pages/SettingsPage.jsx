import { useState, useEffect } from 'react'
import { Settings, Shield, TrendingUp, Clock, Brain, Zap } from 'lucide-react'
import { getSettings, getSettingsSchema, updateSetting, getModules } from '../api/client'

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

  useEffect(() => {
    Promise.all([getSettingsSchema(), getSettings(), getModules()])
      .then(([s, v, m]) => { setSchema(s); setSettings(v); setModules(m) })
      .catch(console.error)
  }, [])

  async function handleChange(key, value) {
    setSaving(key)
    try {
      await updateSetting(key, value)
      // Update local state
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
