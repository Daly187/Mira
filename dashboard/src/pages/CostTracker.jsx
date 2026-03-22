import { useState, useEffect } from 'react'
import { DollarSign, Zap, Brain } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { getCosts } from '../api/client'

const TIER_COLORS = {
  fast: '#22c55e',
  standard: '#3b82f6',
  deep: '#a855f7',
}

const TIER_LABELS = {
  fast: 'Haiku (Fast)',
  standard: 'Sonnet (Standard)',
  deep: 'Opus (Deep)',
}

export default function CostTracker() {
  const [period, setPeriod] = useState('today')
  const [costs, setCosts] = useState(null)

  useEffect(() => {
    getCosts(period).then(setCosts).catch(console.error)
  }, [period])

  const pieData = costs?.by_tier?.map(t => ({
    name: TIER_LABELS[t.tier] || t.tier,
    value: t.cost || 0,
    color: TIER_COLORS[t.tier] || '#6b7280',
    calls: t.calls,
  })) || []

  const barData = costs?.by_task?.map(t => ({
    name: t.task_type,
    cost: t.cost || 0,
    calls: t.calls,
  })) || []

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">API Costs</h1>
      <p className="text-gray-500 text-sm mb-8">Track API spend by model tier and task type</p>

      {/* Period selector */}
      <div className="flex gap-2 mb-8">
        {['today', 'week', 'month', 'all'].map(p => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-4 py-2 rounded-lg text-sm transition ${
              period === p
                ? 'bg-mira-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      {!costs ? (
        <p className="text-gray-500">Loading costs...</p>
      ) : (
        <>
          {/* Total */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
            <div className="flex items-center gap-3 mb-2">
              <DollarSign size={24} className="text-yellow-400" />
              <span className="text-lg text-gray-400">Total ({period})</span>
            </div>
            <div className="text-4xl font-bold text-gray-100">${costs.total_cost.toFixed(4)}</div>
            <div className="text-sm text-gray-500 mt-1">{costs.total_calls} API calls</div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Pie Chart — Cost by Tier */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Zap size={18} className="text-mira-400" /> Cost by Model Tier
              </h3>
              {pieData.length === 0 ? (
                <p className="text-gray-600 text-sm">No API calls yet.</p>
              ) : (
                <div className="flex items-center gap-6">
                  <ResponsiveContainer width="50%" height={200}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        dataKey="value"
                        stroke="none"
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                        labelStyle={{ color: '#9ca3af' }}
                        formatter={(value) => [`$${value.toFixed(4)}`, 'Cost']}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-3">
                    {pieData.map((t, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <div className="w-3 h-3 rounded-full" style={{ background: t.color }} />
                        <div>
                          <div className="text-sm text-gray-300">{t.name}</div>
                          <div className="text-xs text-gray-500">${t.value.toFixed(4)} ({t.calls} calls)</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Bar Chart — Cost by Task Type */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Brain size={18} className="text-blue-400" /> Cost by Task Type
              </h3>
              {barData.length === 0 ? (
                <p className="text-gray-600 text-sm">No API calls yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={barData} layout="vertical" margin={{ left: 100 }}>
                    <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 12 }} tickFormatter={v => `$${v.toFixed(3)}`} />
                    <YAxis type="category" dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} width={95} />
                    <Tooltip
                      contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                      formatter={(value) => [`$${value.toFixed(4)}`, 'Cost']}
                    />
                    <Bar dataKey="cost" fill="#6B4EFF" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Detailed table */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h3 className="text-lg font-semibold mb-4">Detailed Breakdown</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* By Tier */}
              <div>
                <h4 className="text-sm text-gray-500 mb-3">By Tier</h4>
                <div className="space-y-2">
                  {costs.by_tier.map(t => (
                    <div key={t.tier} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full" style={{ background: TIER_COLORS[t.tier] }} />
                        <span className="text-sm text-gray-300">{TIER_LABELS[t.tier] || t.tier}</span>
                        <span className="text-xs text-gray-600">{t.calls} calls</span>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-gray-200">${t.cost?.toFixed(4)}</div>
                        <div className="text-xs text-gray-600">{t.input_tok?.toLocaleString()}in / {t.output_tok?.toLocaleString()}out</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* By Task */}
              <div>
                <h4 className="text-sm text-gray-500 mb-3">By Task</h4>
                <div className="space-y-2">
                  {costs.by_task.map(t => (
                    <div key={t.task_type} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                      <span className="text-sm text-gray-300 font-mono">{t.task_type}</span>
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-gray-500">{t.calls}x</span>
                        <span className="text-sm font-medium text-gray-200">${t.cost?.toFixed(4)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
