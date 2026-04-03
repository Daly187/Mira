import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { setBackendUrl, getBackendUrl } from '../api/client'

// SHA-256 hash of "325232"
const VALID_PIN_HASH = 'a3ec576cb0969f0d53d01378eda09bed13f29dcdba6136d5a1ee2b27f56b7b68'

async function hashPin(pin) {
  const encoder = new TextEncoder()
  const data = encoder.encode(pin)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState('pin') // 'pin' → 'connect'
  const [pin, setPin] = useState('')
  const [token, setToken] = useState('')
  const [backendUrl, setUrl] = useState(getBackendUrl() || '')
  const [error, setError] = useState('')
  const [testing, setTesting] = useState(false)
  const [success, setSuccess] = useState(false)

  // Step 1: PIN verification (client-side)
  const handlePin = async (e) => {
    e.preventDefault()
    setError('')
    const hashed = await hashPin(pin)
    if (hashed === VALID_PIN_HASH) {
      setStep('connect')
    } else {
      setError('Invalid PIN')
      setPin('')
    }
  }

  // Step 2: Backend connection + token auth
  const handleConnect = async (e) => {
    e.preventDefault()
    if (!token.trim()) {
      setError('Please enter your API token')
      return
    }

    setTesting(true)
    setError('')
    setSuccess(false)

    if (backendUrl.trim()) {
      setBackendUrl(backendUrl.trim())
    }

    try {
      const apiBase = backendUrl.trim()
        ? backendUrl.trim().replace(/\/+$/, '') + '/api'
        : '/api'

      const res = await fetch(`${apiBase}/status`, {
        headers: {
          'Authorization': `Bearer ${token.trim()}`,
          'Content-Type': 'application/json',
        },
      })

      if (res.status === 401) {
        setError('Invalid API token')
        setTesting(false)
        return
      }

      if (!res.ok) throw new Error(`Server returned ${res.status}`)

      const contentType = res.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        throw new Error('Backend returned HTML instead of JSON. Check your backend URL.')
      }

      setSuccess(true)
      login(token.trim())
      setTimeout(() => navigate('/', { replace: true }), 300)
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        setError('Cannot reach backend. Make sure Mira is running and the URL is correct.')
      } else {
        setError(err.message)
      }
    }
    setTesting(false)
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-purple-400 mb-2">MIRA</h1>
          <p className="text-gray-500">Autonomous Digital Twin</p>
        </div>

        {step === 'pin' ? (
          <form onSubmit={handlePin} className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-800">
            <h2 className="text-lg font-semibold text-gray-200 mb-4 text-center">Enter PIN</h2>

            <input
              type="password"
              inputMode="numeric"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              placeholder="6-digit PIN"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-4 text-white text-center text-2xl tracking-[0.5em] placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4"
              autoFocus
              required
            />

            {error && <p className="text-red-400 text-sm mb-4 text-center">{error}</p>}

            <button
              type="submit"
              disabled={pin.length < 6}
              className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-3 rounded-lg transition-colors"
            >
              Verify
            </button>
          </form>
        ) : (
          <form onSubmit={handleConnect} className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-800">
            <h2 className="text-lg font-semibold text-gray-200 mb-4">Connect to Mira</h2>

            <label className="block text-sm font-medium text-gray-400 mb-2">
              Backend URL
              <span className="text-gray-600 font-normal ml-1">(leave empty if same machine)</span>
            </label>
            <input
              type="text"
              value={backendUrl}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="http://100.x.x.x:8000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4"
            />

            <label className="block text-sm font-medium text-gray-400 mb-2">API Token</label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter your API token"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4"
              autoFocus
              required
            />

            <p className="text-xs text-gray-600 mb-4">
              Your API token is set in <code className="text-gray-500">agent/.env</code> as <code className="text-gray-500">API_TOKEN</code>
            </p>

            {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
            {success && <p className="text-green-400 text-sm mb-4">Connected successfully!</p>}

            <button
              type="submit"
              disabled={testing}
              className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-3 rounded-lg transition-colors"
            >
              {testing ? 'Connecting...' : 'Connect'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
