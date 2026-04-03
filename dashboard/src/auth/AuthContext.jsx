import { createContext, useContext, useState, useEffect } from 'react'
import { checkAuth, isLoggedIn, logout as apiLogout } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [authenticated, setAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if we have a stored token that's still valid
    async function check() {
      if (isLoggedIn()) {
        const valid = await checkAuth()
        setAuthenticated(valid)
      }
      setLoading(false)
    }
    check()
  }, [])

  const login = (token) => {
    localStorage.setItem('mira_api_token', token)
    setAuthenticated(true)
  }

  const logout = () => {
    setAuthenticated(false)
    apiLogout()
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: authenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
