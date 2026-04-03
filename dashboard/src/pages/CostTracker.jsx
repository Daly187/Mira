import { useState, useEffect, useCallback } from 'react'
import { DollarSign, Zap, Brain, AlertTriangle, RefreshCw, Calendar, Clock, BarChart3 } from 'lucide-react'
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

const TIMEOUT_MS = 5000

export default function CostTracker() {
  const [period, setPeriod] = useState('today')
  const [costs, setCosts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Summary data for the three fixed periods
  const [summaryToday, setSummaryToday] = useState(null)
  const [summaryWeek, setSummaryWeek] = useState(null)
  const [summaryMonth, setSummaryMonth] = useState(null)

  const fetchCosts = useCallback(async (p) => {
    setLoading(true)
    setError(null)
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS)

      const result = await Promise.race([
        getCosts(p),
        new Promise((_, reject) => {
          setTimeout(() => reject(new Error('Request timed out after 5 seconds')), TIMEOUT_MS)
        }),
      ])

      clearTimeout(timeout)
      setCosts(result)
    } catch (e) {
      console.error('Failed to load costs:', e)
      setError(e.message || 'Failed to load cost data')
      setCosts(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch summary totals for the three cards
  useEffect(() => {
    const fetchSummary = async (p) => {
      try {
        const result = await Promise.race([
          getCosts(p),
          new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), TIMEOUT_MS)),
        ])
        return result
      } catch {
        return null
      }
    }

    fetchSummary('today').then(setSummaryToday)
    fetchSummary('week').then(setSummaryWeek)
    fetchSummary('month').then(setSummaryMonth)
  }, [])

  useEffect(() => {
    fetchCosts(period)
  }, [period, fetchCosts])

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

  // Build a flat table from by_tier + by_task data
  const tableRows = []
  if (costs?.by_tier) {
    costs.by_tier.forEach(t => {
      tableRows.push({
        model: TIER_LABELS[t.tier] || t.tier,
        tier: t.tier,
        task_type: '--',
        tokens: (t.input_tok || 0) + (t.output_tok || 0),
        input_tok: t.input_tok || 0,
        output_tok: t.output_tok || 0,
        cost: t.cost || 0,
        calls: t.calls || 0,
      })
    })
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">API Costs</h1>
      <p className="text-gray-500 text-sm mb-8">Track API spend by model tier and task type</p>

      {/* Summary Cards — always visible */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gray-800 text-green-400">
              <Clock size={18} />
            </div>
            <span className="text-sm text-gray-400">Total Today</span>
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {summaryToday ? `$${summaryToday.total_cost.toFixed(4)}` : '--'}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {summaryToday ? `${summaryToday.total_calls} calls` : 'Loading...'}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gray-800 text-blue-400">
              <Calendar size={18} />
            </div>
            <span className="text-sm text-gray-400">Total Week</span>
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {summaryWeek ? `$${summaryWeek.total_cost.toFixed(4)}` : '--'}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {summaryWeek ? `${summaryWeek.total_calls} calls` : 'Loading...'}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-gray-800 text-mira-400">
              <BarChart3 size={18} />
            </div>
            <span className="text-sm text-gray-400">Total Month</span>
          </div>
          <div className="text-2xl font-bold text-gray-100">
            {summaryMonth ? `$${summaryMonth.total_cost.toFixed(4)}` : '--'}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {summaryMonth ? `${summaryMonth.total_calls} calls` : 'Loading...'}
          </p>
        </div>
      </div>

      {/* Period selector */}
      <div className="flex items-center gap-2 mb-8">
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
        {error && (
          <button
            onClick={() => fetchCosts(period)}
            className="ml-auto flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-gray-800 text-gray-400 hover:bg-gray-700 transition"
          >
            <RefreshCw size={14} /> Retry
          </button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle size={20} className="text-red-400" />
            <span className="text-red-300 font-medium">Failed to load cost data</span>
          </div>
          <p className="text-sm text-red-400/80">{error}</p>
          <p className="text-xs text-gray-500 mt-2">Make sure the FastAPI server is running on port 8000.</p>
        </div>
      )}

      {/* Loading state */}
      {loading && !error && (
        <div className="text-center py-16">
          <div className="inline-block w-8 h-8 border-2 border-mira-500 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-gray-500">Loading costs...</p>
        </div>
      )}

      {/* Empty state — API responded but no data */}
      {!loading && !error && costs && costs.total_calls === 0 && (
        <div className="text-center py-16">
          <DollarSign size={40} className="mx-auto text-gray-700 mb-4" />
          <h2 className="text-xl text-gray-400 mb-2">No API costs recorded yet</h2>
          <p className="text-gray-600 text-sm">Costs will appear here once Mira starts making API calls.</p>
        </div>
      )}

      {/* Data loaded and has content */}
      {!loading && !error && costs && costs.total_calls > 0 && (
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

          {/* Cost Breakdown Table */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
            <h3 className="text-lg font-semibold mb-4">Cost Breakdown</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-800">
                    <th className="pb-3 pr-4 font-medium">Model</th>
                    <th className="pb-3 pr-4 font-medium">Tier</th>
                    <th className="pb-3 pr-4 font-medium text-right">Calls</th>
                    <th className="pb-3 pr-4 font-medium text-right">Input Tokens</th>
                    <th className="pb-3 pr-4 font-medium text-right">Output Tokens</th>
                    <th className="pb-3 font-medium text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row, i) => (
                    <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                      <td className="py-3 pr-4 text-gray-300">{row.model}</td>
                      <td className="py-3 pr-4">
                        <span
                          className="inline-block w-2 h-2 rounded-full mr-2"
                          style={{ background: TIER_COLORS[row.tier] || '#6b7280' }}
                        />
                        <span className="text-gray-400">{row.tier}</span>
                      </td>
                      <td className="py-3 pr-4 text-right text-gray-400">{row.calls}</td>
                      <td className="py-3 pr-4 text-right text-gray-400">{row.input_tok.toLocaleString()}</td>
                      <td className="py-3 pr-4 text-right text-gray-400">{row.output_tok.toLocaleString()}</td>
                      <td className="py-3 text-right font-medium text-gray-200">${row.cost.toFixed(4)}</td>
                    </tr>
                  ))}
                  {tableRows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-gray-600">No cost data for this period.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detailed Breakdown */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h3 className="text-lg font-semibold mb-4">Detailed Breakdown</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* By Tier */}
              <div>
                <h4 className="text-sm text-gray-500 mb-3">By Tier</h4>
                <div className="space-y-2">
                  {(costs.by_tier || []).map(t => (
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
                  {(costs.by_task || []).map(t => (
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
