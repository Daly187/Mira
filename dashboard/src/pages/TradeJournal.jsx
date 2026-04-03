import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, AlertCircle, PieChart, BarChart3, Plus, ArrowUpDown, Filter } from 'lucide-react'
import { getTrades, getOpenTrades, createTrade } from '../api/client'

export default function TradeJournal() {
  const [trades, setTrades] = useState([])
  const [openTrades, setOpenTrades] = useState([])
  const [tab, setTab] = useState('overview')
  const [showAdd, setShowAdd] = useState(false)
  const [newTrade, setNewTrade] = useState({
    instrument: '', direction: 'buy', entry_price: '', size: '',
    strategy: '', platform: 'mt5', rationale: '',
  })

  // History filters/sort
  const [historyFilter, setHistoryFilter] = useState({ strategy: '', direction: '' })
  const [historySort, setHistorySort] = useState('date') // date | pnl | instrument
  const [historySortDir, setHistorySortDir] = useState('desc')

  async function loadData() {
    try {
      const [t, o] = await Promise.all([getTrades(100), getOpenTrades()])
      setTrades(t)
      setOpenTrades(o)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { loadData() }, [])

  const closedTrades = trades.filter(t => t.pnl !== null)
  const totalPnl = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0)
  const winners = closedTrades.filter(t => t.pnl > 0).length
  const winRate = closedTrades.length > 0 ? (winners / closedTrades.length * 100) : null

  // Platform breakdown
  const byPlatform = {}
  openTrades.forEach(t => {
    const p = t.platform || 'mt5'
    if (!byPlatform[p]) byPlatform[p] = { count: 0, notional: 0 }
    byPlatform[p].count += 1
    byPlatform[p].notional += (t.entry_price || 0) * (t.size || 0)
  })

  // Strategy breakdown (closed)
  const byStrategy = {}
  closedTrades.forEach(t => {
    const s = t.strategy || 'manual'
    if (!byStrategy[s]) byStrategy[s] = { count: 0, pnl: 0, wins: 0 }
    byStrategy[s].count += 1
    byStrategy[s].pnl += t.pnl || 0
    if ((t.pnl || 0) > 0) byStrategy[s].wins += 1
  })

  // DCA positions
  const dcaTrades = openTrades.filter(t => (t.strategy || '').toLowerCase().includes('dca'))
  const dcaByInstrument = {}
  dcaTrades.forEach(t => {
    const inst = t.instrument
    if (!dcaByInstrument[inst]) dcaByInstrument[inst] = { size: 0, cost: 0, count: 0 }
    dcaByInstrument[inst].size += t.size || 0
    dcaByInstrument[inst].cost += (t.entry_price || 0) * (t.size || 0)
    dcaByInstrument[inst].count += 1
  })

  // Filter and sort closed trades for history tab
  const strategies = [...new Set(closedTrades.map(t => t.strategy || 'manual'))]
  const filteredHistory = closedTrades
    .filter(t => !historyFilter.strategy || (t.strategy || 'manual') === historyFilter.strategy)
    .filter(t => !historyFilter.direction || t.direction === historyFilter.direction)
    .sort((a, b) => {
      let cmp = 0
      if (historySort === 'date') {
        cmp = (a.opened_at || '').localeCompare(b.opened_at || '')
      } else if (historySort === 'pnl') {
        cmp = (a.pnl || 0) - (b.pnl || 0)
      } else if (historySort === 'instrument') {
        cmp = (a.instrument || '').localeCompare(b.instrument || '')
      }
      return historySortDir === 'asc' ? cmp : -cmp
    })

  function toggleHistorySort(field) {
    if (historySort === field) {
      setHistorySortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setHistorySort(field)
      setHistorySortDir('desc')
    }
  }

  async function handleAddTrade() {
    if (!newTrade.instrument.trim()) return
    try {
      await createTrade({
        instrument: newTrade.instrument,
        direction: newTrade.direction,
        entry_price: newTrade.entry_price ? parseFloat(newTrade.entry_price) : undefined,
        size: newTrade.size ? parseFloat(newTrade.size) : undefined,
        strategy: newTrade.strategy || undefined,
        platform: newTrade.platform,
        rationale: newTrade.rationale || undefined,
      })
      setNewTrade({ instrument: '', direction: 'buy', entry_price: '', size: '', strategy: '', platform: 'mt5', rationale: '' })
      setShowAdd(false)
      await loadData()
    } catch (e) {
      console.error('Failed to log trade:', e)
    }
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'open', label: `Open (${openTrades.length})` },
    { id: 'history', label: `History (${closedTrades.length})` },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold">Trade Journal</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm"
        >
          <Plus size={16} /> Log Trade
        </button>
      </div>
      <p className="text-gray-500 text-sm mb-6">Every trade logged with full context and rationale</p>

      {/* Add Trade Form */}
      {showAdd && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Log New Trade</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <input
              value={newTrade.instrument}
              onChange={(e) => setNewTrade({ ...newTrade, instrument: e.target.value })}
              placeholder="Instrument (e.g. BTCUSD, EURUSD) *"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <select
              value={newTrade.direction}
              onChange={(e) => setNewTrade({ ...newTrade, direction: e.target.value })}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            >
              <option value="buy">Buy (Long)</option>
              <option value="sell">Sell (Short)</option>
            </select>
            <input
              type="number"
              step="any"
              value={newTrade.entry_price}
              onChange={(e) => setNewTrade({ ...newTrade, entry_price: e.target.value })}
              placeholder="Entry Price"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <input
              type="number"
              step="any"
              value={newTrade.size}
              onChange={(e) => setNewTrade({ ...newTrade, size: e.target.value })}
              placeholder="Size / Lots"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <input
              value={newTrade.strategy}
              onChange={(e) => setNewTrade({ ...newTrade, strategy: e.target.value })}
              placeholder="Strategy (e.g. dca, breakout, scalp)"
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
            <select
              value={newTrade.platform}
              onChange={(e) => setNewTrade({ ...newTrade, platform: e.target.value })}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
            >
              <option value="mt5">MT5</option>
              <option value="binance">Binance</option>
              <option value="kraken">Kraken</option>
              <option value="polymarket">Polymarket</option>
              <option value="other">Other</option>
            </select>
          </div>
          <textarea
            value={newTrade.rationale}
            onChange={(e) => setNewTrade({ ...newTrade, rationale: e.target.value })}
            placeholder="Rationale / trade thesis (why are you taking this trade?)"
            rows={2}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 text-gray-400 hover:text-gray-200 text-sm"
            >
              Cancel
            </button>
            <button onClick={handleAddTrade} className="px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm">
              Log Trade
            </button>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500">Total P&L</p>
          <p className={`text-2xl font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${totalPnl.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500">Win Rate</p>
          <p className="text-2xl font-bold text-gray-200">
            {winRate !== null ? `${winRate.toFixed(1)}%` : 'N/A'}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500">Total Trades</p>
          <p className="text-2xl font-bold text-gray-200">{closedTrades.length}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500">Open Positions</p>
          <p className="text-2xl font-bold text-mira-400">{openTrades.length}</p>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-2 mb-6">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === t.id
                ? 'bg-mira-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {Object.keys(byPlatform).length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <PieChart size={14} /> Open Positions by Platform
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {Object.entries(byPlatform).map(([platform, data]) => (
                  <div key={platform} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                    <p className="text-xs text-gray-500 uppercase">{platform}</p>
                    <p className="text-xl font-bold text-gray-200">{data.count}</p>
                    <p className="text-xs text-gray-600">${data.notional.toFixed(2)} notional</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {Object.keys(byStrategy).length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <BarChart3 size={14} /> Performance by Strategy
              </h2>
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800/50">
                    <tr className="text-gray-400 text-xs">
                      <th className="text-left p-3">Strategy</th>
                      <th className="text-center p-3">Trades</th>
                      <th className="text-center p-3">Win Rate</th>
                      <th className="text-right p-3">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(byStrategy)
                      .sort(([, a], [, b]) => b.pnl - a.pnl)
                      .map(([strategy, data]) => (
                        <tr key={strategy} className="border-t border-gray-800">
                          <td className="p-3 text-gray-200 capitalize">{strategy}</td>
                          <td className="p-3 text-center text-gray-400">{data.count}</td>
                          <td className="p-3 text-center text-gray-400">
                            {(data.wins / data.count * 100).toFixed(0)}%
                          </td>
                          <td className={`p-3 text-right font-medium ${data.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ${data.pnl.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {Object.keys(dcaByInstrument).length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                DCA Positions
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(dcaByInstrument).map(([inst, data]) => {
                  const avgEntry = data.size > 0 ? data.cost / data.size : 0
                  return (
                    <div key={inst} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                      <p className="text-sm font-medium text-gray-200">{inst}</p>
                      <p className="text-xs text-gray-500">{data.count} buys</p>
                      <p className="text-xs text-gray-400">
                        Size: {data.size.toFixed(4)} | Avg: ${avgEntry.toFixed(2)}
                      </p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {trades.length === 0 && openTrades.length === 0 && (
            <div className="text-center py-12 text-gray-600">
              <TrendingUp size={48} className="mx-auto mb-4 opacity-30" />
              <p>No trades logged yet. Use the "Log Trade" button to get started.</p>
            </div>
          )}
        </div>
      )}

      {/* Open Positions Tab */}
      {tab === 'open' && (
        <>
          {openTrades.length === 0 ? (
            <p className="text-gray-600">No open positions.</p>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-800/50">
                  <tr className="text-gray-400 text-xs">
                    <th className="text-left p-3">Instrument</th>
                    <th className="text-left p-3">Direction</th>
                    <th className="text-left p-3">Entry</th>
                    <th className="text-left p-3">Size</th>
                    <th className="text-left p-3">Strategy</th>
                    <th className="text-left p-3">Platform</th>
                    <th className="text-left p-3">Opened</th>
                  </tr>
                </thead>
                <tbody>
                  {openTrades.map(t => (
                    <tr key={t.id} className="border-t border-gray-800">
                      <td className="p-3 font-medium text-gray-200">{t.instrument}</td>
                      <td className="p-3">
                        <span className={`flex items-center gap-1 ${t.direction === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                          {t.direction === 'buy' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                          {t.direction}
                        </span>
                      </td>
                      <td className="p-3 text-gray-300">{t.entry_price}</td>
                      <td className="p-3 text-gray-300">{t.size}</td>
                      <td className="p-3 text-gray-500">{t.strategy || '-'}</td>
                      <td className="p-3">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">
                          {t.platform || 'mt5'}
                        </span>
                      </td>
                      <td className="p-3 text-gray-500 text-xs">{t.opened_at?.substring(0, 16)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* History Tab */}
      {tab === 'history' && (
        <>
          {/* Filter and sort controls */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex items-center gap-1">
              <Filter size={14} className="text-gray-500" />
              <select
                value={historyFilter.strategy}
                onChange={(e) => setHistoryFilter({ ...historyFilter, strategy: e.target.value })}
                className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5 text-sm text-gray-300"
              >
                <option value="">All strategies</option>
                {strategies.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <select
                value={historyFilter.direction}
                onChange={(e) => setHistoryFilter({ ...historyFilter, direction: e.target.value })}
                className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5 text-sm text-gray-300"
              >
                <option value="">All directions</option>
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div className="flex items-center gap-1 ml-auto">
              <ArrowUpDown size={14} className="text-gray-500" />
              {['date', 'pnl', 'instrument'].map(field => (
                <button
                  key={field}
                  onClick={() => toggleHistorySort(field)}
                  className={`px-2 py-1 rounded text-xs ${historySort === field ? 'bg-mira-500/20 text-mira-300' : 'bg-gray-800 text-gray-400'}`}
                >
                  {field.charAt(0).toUpperCase() + field.slice(1)} {historySort === field ? (historySortDir === 'asc' ? '\u2191' : '\u2193') : ''}
                </button>
              ))}
            </div>
          </div>

          <p className="text-xs text-gray-600 mb-3">{filteredHistory.length} trade{filteredHistory.length !== 1 ? 's' : ''} shown</p>

          {filteredHistory.length === 0 ? (
            <p className="text-gray-600">
              {closedTrades.length === 0 ? 'No closed trades yet.' : 'No trades match your filters.'}
            </p>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-800/50">
                  <tr className="text-gray-400 text-xs">
                    <th className="text-left p-3">Instrument</th>
                    <th className="text-left p-3">Direction</th>
                    <th className="text-left p-3">Entry</th>
                    <th className="text-left p-3">Exit</th>
                    <th className="text-left p-3">P&L</th>
                    <th className="text-left p-3">Strategy</th>
                    <th className="text-left p-3">Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map(t => (
                    <tr key={t.id} className="border-t border-gray-800">
                      <td className="p-3 font-medium text-gray-200">{t.instrument}</td>
                      <td className="p-3">
                        <span className={t.direction === 'buy' ? 'text-green-400' : 'text-red-400'}>
                          {t.direction}
                        </span>
                      </td>
                      <td className="p-3 text-gray-300">{t.entry_price}</td>
                      <td className="p-3 text-gray-300">{t.exit_price}</td>
                      <td className={`p-3 font-medium ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${t.pnl?.toFixed(2)}
                      </td>
                      <td className="p-3 text-gray-500">{t.strategy || '-'}</td>
                      <td className="p-3 text-gray-500 max-w-xs truncate">{t.rationale || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
