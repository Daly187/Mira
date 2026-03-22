import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import { getTrades, getOpenTrades } from '../api/client'

export default function TradeJournal() {
  const [trades, setTrades] = useState([])
  const [openTrades, setOpenTrades] = useState([])

  useEffect(() => {
    Promise.all([getTrades(100), getOpenTrades()])
      .then(([t, o]) => { setTrades(t); setOpenTrades(o) })
      .catch(console.error)
  }, [])

  const closedTrades = trades.filter(t => t.pnl !== null)
  const totalPnl = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0)
  const winners = closedTrades.filter(t => t.pnl > 0).length
  const winRate = closedTrades.length > 0 ? (winners / closedTrades.length * 100) : 0

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Trade Journal</h1>
      <p className="text-gray-500 text-sm mb-8">Every trade logged with full context and rationale</p>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500">Total P&L</p>
          <p className={`text-2xl font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${totalPnl.toFixed(2)}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500">Win Rate</p>
          <p className="text-2xl font-bold text-gray-200">{winRate.toFixed(1)}%</p>
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

      {/* Open Trades */}
      {openTrades.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <AlertCircle size={18} className="text-yellow-400" /> Open Positions
          </h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/50">
                <tr className="text-gray-400 text-xs">
                  <th className="text-left p-3">Instrument</th>
                  <th className="text-left p-3">Direction</th>
                  <th className="text-left p-3">Entry</th>
                  <th className="text-left p-3">Size</th>
                  <th className="text-left p-3">Strategy</th>
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
                    <td className="p-3 text-gray-500">{t.opened_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trade History */}
      <h2 className="text-lg font-semibold mb-4">Trade History</h2>
      {closedTrades.length === 0 ? (
        <p className="text-gray-600">No closed trades yet.</p>
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
              {closedTrades.map(t => (
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
    </div>
  )
}
