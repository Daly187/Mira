import { useState, useEffect } from 'react'
import { Scale, CheckCircle, Clock, BarChart3, Plus, X, AlertCircle, Filter } from 'lucide-react'
import { getDecisions, scoreDecision, createDecision } from '../api/client'

const DOMAINS = ['general', 'trading', 'career', 'health', 'finance', 'relationships', 'tech', 'business']

export default function DecisionJournal() {
  const [decisions, setDecisions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [scoring, setScoring] = useState(null)
  const [scoringLoading, setScoringLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [filterDomain, setFilterDomain] = useState('all')

  // Create form state
  const [formDecision, setFormDecision] = useState('')
  const [formContext, setFormContext] = useState('')
  const [formDomain, setFormDomain] = useState('general')
  const [formAlternatives, setFormAlternatives] = useState('')
  const [formError, setFormError] = useState(null)
  const [formSubmitting, setFormSubmitting] = useState(false)

  const load = () => {
    setError(null)
    getDecisions(100)
      .then(setDecisions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleScore = async () => {
    if (!scoring) return
    setScoringLoading(true)
    try {
      await scoreDecision(scoring.id, scoring.score, scoring.outcome)
      setScoring(null)
      load()
    } catch (e) {
      setError(`Failed to score decision: ${e.message}`)
    } finally {
      setScoringLoading(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!formDecision.trim()) {
      setFormError('Decision text is required')
      return
    }
    setFormSubmitting(true)
    setFormError(null)
    try {
      const alternatives = formAlternatives
        .split('\n')
        .map((a) => a.trim())
        .filter(Boolean)
      await createDecision({
        decision: formDecision.trim(),
        context: formContext.trim(),
        domain: formDomain,
        alternatives_considered: alternatives,
      })
      setFormDecision('')
      setFormContext('')
      setFormDomain('general')
      setFormAlternatives('')
      setShowForm(false)
      load()
    } catch (e) {
      setFormError(e.message)
    } finally {
      setFormSubmitting(false)
    }
  }

  // Filter by domain
  const filtered = filterDomain === 'all'
    ? decisions
    : decisions.filter((d) => d.domain === filterDomain)

  const scored = filtered.filter((d) => d.outcome_score !== null)
  const unscored = filtered.filter((d) => d.outcome_score === null)
  const avgScore = scored.length
    ? (scored.reduce((s, d) => s + d.outcome_score, 0) / scored.length).toFixed(1)
    : null

  // Domain breakdown (from all decisions, not filtered)
  const allScored = decisions.filter((d) => d.outcome_score !== null)
  const domains = {}
  allScored.forEach((d) => {
    const dom = d.domain || 'general'
    if (!domains[dom]) domains[dom] = { total: 0, count: 0 }
    domains[dom].total += d.outcome_score
    domains[dom].count += 1
  })

  // Unique domains in data for filter
  const uniqueDomains = [...new Set(decisions.map((d) => d.domain || 'general'))]

  const scoreColor = (score) => {
    if (score >= 8) return 'text-green-400'
    if (score >= 5) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold">Decision Journal</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white text-sm rounded-lg transition"
        >
          {showForm ? <X size={16} /> : <Plus size={16} />}
          {showForm ? 'Cancel' : 'Add Decision'}
        </button>
      </div>
      <p className="text-gray-500 text-sm mb-6">Track decisions, score outcomes, identify blind spots</p>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-800 text-red-300 text-sm rounded-lg px-4 py-3 mb-6">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Add Decision form */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Log a Decision</h2>
          {formError && (
            <div className="text-red-400 text-sm mb-3 flex items-center gap-1">
              <AlertCircle size={14} /> {formError}
            </div>
          )}
          <div className="space-y-4 mb-4">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Decision</label>
              <textarea
                value={formDecision}
                onChange={(e) => setFormDecision(e.target.value)}
                placeholder="What did you decide?"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-mira-500 focus:outline-none"
                rows={2}
                autoFocus
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Context / Reasoning</label>
                <textarea
                  value={formContext}
                  onChange={(e) => setFormContext(e.target.value)}
                  placeholder="Why? What were you thinking at the time?"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-mira-500 focus:outline-none"
                  rows={3}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Alternatives Considered (one per line)</label>
                <textarea
                  value={formAlternatives}
                  onChange={(e) => setFormAlternatives(e.target.value)}
                  placeholder="Option A&#10;Option B&#10;Do nothing"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-mira-500 focus:outline-none"
                  rows={3}
                />
              </div>
            </div>
            <div className="max-w-xs">
              <label className="text-xs text-gray-500 block mb-1">Domain</label>
              <select
                value={formDomain}
                onChange={(e) => setFormDomain(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-mira-500 focus:outline-none"
              >
                {DOMAINS.map((d) => (
                  <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={formSubmitting}
              className="px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white text-sm rounded-lg transition disabled:opacity-50"
            >
              {formSubmitting ? 'Saving...' : 'Log Decision'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : decisions.length === 0 ? (
        <div className="text-center py-16 text-gray-600">
          <Scale size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg">No decisions logged yet.</p>
          <p className="text-sm mt-2 text-gray-500 mb-4">
            Start tracking your decisions to identify patterns and improve over time.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white text-sm rounded-lg transition"
          >
            <Plus size={16} /> Log your first decision
          </button>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Total Decisions</p>
              <p className="text-2xl font-bold mt-1">{decisions.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Avg Score</p>
              <p className={`text-2xl font-bold mt-1 ${avgScore ? scoreColor(parseFloat(avgScore)) : ''}`}>
                {avgScore ? `${avgScore}/10` : '--'}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Scored</p>
              <p className="text-2xl font-bold mt-1 text-green-400">{allScored.length}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-gray-500 text-xs uppercase tracking-wider">Awaiting Review</p>
              <p className="text-2xl font-bold mt-1 text-yellow-400">
                {decisions.filter((d) => d.outcome_score === null).length}
              </p>
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

          {/* Domain filter */}
          {uniqueDomains.length > 1 && (
            <div className="flex items-center gap-2 mb-6">
              <Filter size={14} className="text-gray-500" />
              <span className="text-xs text-gray-500 uppercase tracking-wider mr-2">Filter:</span>
              <button
                onClick={() => setFilterDomain('all')}
                className={`px-3 py-1 text-xs rounded-full transition ${
                  filterDomain === 'all'
                    ? 'bg-mira-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                All
              </button>
              {uniqueDomains.sort().map((d) => (
                <button
                  key={d}
                  onClick={() => setFilterDomain(d)}
                  className={`px-3 py-1 text-xs rounded-full capitalize transition ${
                    filterDomain === d
                      ? 'bg-mira-500 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  {d}
                </button>
              ))}
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
                      <th className="text-left px-4 py-3">Decision</th>
                      <th className="text-center px-4 py-3">Domain</th>
                      <th className="text-center px-4 py-3">Date</th>
                      <th className="text-right px-4 py-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unscored.map((d) => (
                      <tr key={d.id} className="border-t border-gray-800 hover:bg-gray-800/30 transition">
                        <td className="px-4 py-3">
                          <p className="text-gray-200">{d.decision?.substring(0, 100)}</p>
                          {d.context && (
                            <p className="text-gray-500 text-xs mt-1">{d.context.substring(0, 80)}</p>
                          )}
                        </td>
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
                            onClick={() => setScoring({ id: d.id, score: 5, outcome: '', decision: d.decision })}
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
                      <tr key={d.id} className="border-t border-gray-800 hover:bg-gray-800/30 transition">
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
                        <td className="px-4 py-3 text-gray-400 text-xs">{d.outcome?.substring(0, 60) || '--'}</td>
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
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setScoring(null)}>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-bold mb-2">Score Decision #{scoring.id}</h3>
                {scoring.decision && (
                  <p className="text-gray-400 text-sm mb-4 border-l-2 border-gray-700 pl-3">
                    {scoring.decision.substring(0, 150)}
                  </p>
                )}

                <label className="text-sm text-gray-400 block mb-2">
                  Outcome Score (1-10)
                </label>
                <div className="flex gap-1 mb-4">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <button
                      key={n}
                      onClick={() => setScoring({ ...scoring, score: n })}
                      className={`w-9 h-9 rounded-lg text-sm font-bold transition ${
                        scoring.score === n
                          ? n >= 8
                            ? 'bg-green-500 text-white'
                            : n >= 5
                            ? 'bg-yellow-500 text-white'
                            : 'bg-red-500 text-white'
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
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 mb-4 focus:border-mira-500 focus:outline-none"
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
                    disabled={scoringLoading}
                    className="px-4 py-2 bg-mira-500 text-white rounded-lg text-sm hover:bg-mira-600 transition disabled:opacity-50"
                  >
                    {scoringLoading ? 'Saving...' : 'Save Score'}
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
