import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, checkAuth, setBackendUrl, getBackendUrl, getBackendUrl as getUrl } from '../api/client'

export default function LoginPage() {
  const [token, setToken] = useState('')
  const [backendUrl, setUrl] = useState(getBackendUrl() || '')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  // Check if already authenticated
  useEffect(() => {
    checkAuth().then(ok => {
      if (ok) navigate('/', { replace: true })
      else setLoading(false)
    })
  }, [])

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // Save backend URL first (so API calls use it)
    const cleanUrl = backendUrl.trim().replace(/\/+$/, '')
    if (cleanUrl) {
      setBackendUrl(cleanUrl)
    } else {
      setBackendUrl(null)
    }

    // Build the API base from the URL
    const apiBase = cleanUrl ? `${cleanUrl}/api` : '/api'

    try {
      const res = await fetch(`${apiBase}/status`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      })

      if (res.ok) {
        if (token) login(token)
        navigate('/', { replace: true })
      } else if (res.status === 401) {
        setError('Invalid API token')
        setLoading(false)
      } else {
        setError(`Cannot connect (HTTP ${res.status})`)
        setLoading(false)
      }
    } catch (err) {
      setError(
        cleanUrl
          ? `Cannot reach ${cleanUrl} — check the URL and ensure Mira is running`
          : 'Cannot connect to Mira API — is it running on this machine?'
      )
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-500">Connecting...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-purple-400 mb-2">MIRA</h1>
          <p className="text-gray-500">Autonomous Digital Twin</p>
        </div>

        <form onSubmit={handleLogin} className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-800">
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Backend URL
          </label>
          <input
            type="url"
            value={backendUrl}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://your-mira-backend.com"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-1"
          />
          <p className="text-gray-600 text-xs mb-4">
            Your Windows desktop IP or Cloudflare Tunnel URL. Leave blank if running locally.
          </p>

          <label className="block text-sm font-medium text-gray-400 mb-2">
            API Token
          </label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter your API token"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4"
            autoFocus
          />

          {error && (
            <p className="text-red-400 text-sm mb-4">{error}</p>
          )}

          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-3 rounded-lg transition-colors"
          >
            Connect to Mira
          </button>

          <p className="text-gray-600 text-xs mt-4 text-center">
            Set API_TOKEN in your .env file on the Windows desktop
          </p>
        </form>
      </div>
    </div>
  )
}
