import { useState, useEffect } from 'react'
import { Scale, Star, CheckCircle, Clock, BarChart3 } from 'lucide-react'
import { getDecisions, scoreDecision } from '../api/client'

export default function DecisionJournal() {
  const [decisions, setDecisions] = useState([])
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(null) // { id, score, outcome }

  const load = () => {
    getDecisions(100)
      .then(setDecisions)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleScore = async () => {
    if (!scoring) return
    try {
      await scoreDecision(scoring.id, scoring.score, scoring.outcome)
      setScoring(null)
      load()
    } catch (e) {
      console.error(e)
    }
  }

  const scored = decisions.filter((d) => d.outcome_score !== null)
  const unscored = decisions.filter((d) => d.outcome_score === null)
  const avgScore = scored.length
    ? (scored.reduce((s, d) => s + d.outcome_score, 0) / scored.length).toFixed(1)
    : '—'

  // Domain breakdown
  const domains = {}
  scored.forEach((d) => {
    const dom = d.domain || 'general'
    if (!domains[dom]) domains[dom] = { total: 0, count: 0 }
    domains[dom].total += d.outcome_score
    domains[dom].count += 1
  })

  const scoreColor = (score) => {
    if (score >= 8) return 'text-green-400'
    if (score >= 5) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Decision Journal</h1>
      <p className="text-gray-500 text-sm mb-8">Track decisions, score outcomes, identify blind spots</p>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : decisions.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Scale size={48} className="mx-auto mb-4 opacity-30" />
          <p>No decisions logged yet.</p>
          <p className="text-sm mt-2">Use <code className="text-mira-400">/decision [text]</code> in Telegram to log one.</p>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Total Decisions</p>
              <p className="text-2xl font-bold mt-1">{decisions.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Avg Score</p>
              <p className={`text-2xl font-bold mt-1 ${typeof avgScore === 'string' ? '' : scoreColor(avgScore)}`}>
                {avgScore}/10
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Scored</p>
              <p className="text-2xl font-bold mt-1 text-green-400">{scored.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Awaiting Review</p>
              <p className="text-2xl font-bold mt-1 text-yellow-400">{unscored.length}</p>
            </div>
          </div>

          {/* Domain breakdown */}
          {Object.keys(domains).length > 0 && (
            <div className="mb-8">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                <BarChart3 size={14} className="inline mr-2" />
                Score by Domain
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {Object.entries(domains)
                  .sort(([, a], [, b]) => b.total / b.count - a.total / a.count)
                  .map(([domain, data]) => {
                    const avg = (data.total / data.count).toFixed(1)
                    return (
                      <div key={domain} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                        <p className="text-xs text-gray-500 capitalize">{domain}</p>
                        <p className={`text-xl font-bold ${scoreColor(parseFloat(avg))}`}>{avg}</p>
                        <p className="text-xs text-gray-600">{data.count} decisions</p>
                      </div>
                    )
                  })}
              </div>
            </div>
          )}

          {/* Unscored decisions */}
          {unscored.length > 0 && (
            <div className="mb-8">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                <Clock size={14} className="inline mr-2" />
                Awaiting Score ({unscored.length})
              </h2>
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase bg-gray-800/50">
                      <th className="text-left px-4 py-3">ID</th>
                      <th className="text-left px-4 py-3">Decision</th>
                      <th className="text-center px-4 py-3">Domain</th>
                      <th className="text-center px-4 py-3">Date</th>
                      <th className="text-right px-4 py-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unscored.slice(0, 10).map((d) => (
                      <tr key={d.id} className="border-t border-gray-800">
                        <td className="px-4 py-3 text-gray-500 font-mono">#{d.id}</td>
                        <td className="px-4 py-3 text-gray-200">{d.decision?.substring(0, 80)}</td>
                        <td className="px-4 py-3 text-center">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 capitalize">
                            {d.domain}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center text-gray-500 text-xs">
                          {d.decided_at?.substring(0, 10)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => setScoring({ id: d.id, score: 5, outcome: '' })}
                            className="px-3 py-1 bg-mira-500 hover:bg-mira-600 text-white text-xs rounded-lg transition"
                          >
                            Score
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Scored decisions */}
          {scored.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                <CheckCircle size={14} className="inline mr-2" />
                Scored Decisions ({scored.length})
              </h2>
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase bg-gray-800/50">
                      <th className="text-left px-4 py-3">Decision</th>
                      <th className="text-center px-4 py-3">Domain</th>
                      <th className="text-center px-4 py-3">Score</th>
                      <th className="text-left px-4 py-3">Outcome</th>
                      <th className="text-center px-4 py-3">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scored.map((d) => (
                      <tr key={d.id} className="border-t border-gray-800">
                        <td className="px-4 py-3 text-gray-200">{d.decision?.substring(0, 60)}</td>
                        <td className="px-4 py-3 text-center">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 capitalize">
                            {d.domain}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`font-bold ${scoreColor(d.outcome_score)}`}>
                            {d.outcome_score}/10
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs">{d.outcome?.substring(0, 60) || '—'}</td>
                        <td className="px-4 py-3 text-center text-gray-500 text-xs">
                          {d.decided_at?.substring(0, 10)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Scoring modal */}
          {scoring && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md">
                <h3 className="text-lg font-bold mb-4">Score Decision #{scoring.id}</h3>

                <label className="text-sm text-gray-400 block mb-2">
                  Score (1-10)
                </label>
                <div className="flex gap-1 mb-4">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <button
                      key={n}
                      onClick={() => setScoring({ ...scoring, score: n })}
                      className={`w-9 h-9 rounded-lg text-sm font-bold transition ${
                        scoring.score === n
                          ? 'bg-mira-500 text-white'
                          : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>

                <label className="text-sm text-gray-400 block mb-2">
                  Outcome (what happened?)
                </label>
                <textarea
                  value={scoring.outcome}
                  onChange={(e) => setScoring({ ...scoring, outcome: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 mb-4"
                  rows={3}
                  placeholder="Describe what happened..."
                />

                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setScoring(null)}
                    className="px-4 py-2 bg-gray-800 text-gray-400 rounded-lg text-sm hover:bg-gray-700 transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleScore}
                    className="px-4 py-2 bg-mira-500 text-white rounded-lg text-sm hover:bg-mira-600 transition"
                  >
                    Save Score
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
