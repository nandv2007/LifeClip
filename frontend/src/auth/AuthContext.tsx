import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../lib/api'
import { resetSessionToken } from '../lib/session'
import type { AuthUser } from '../lib/types'

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  startupError: string
  signIn: (identifier: string, password: string) => Promise<void>
  signUp: (username: string, email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  clearUser: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [startupError, setStartupError] = useState('')

  useEffect(() => {
    let alive = true
    const authRequired = () => {
      if (alive) setUser(null)
    }
    window.addEventListener('lifeclip:auth-required', authRequired)
    api.me()
      .then((current) => {
        if (alive) setUser(current)
      })
      .catch((error: Error & { status?: number }) => {
        if (alive && error.status !== 401) {
          setStartupError(error.message || 'LifeClip could not reach the server.')
        }
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
      window.removeEventListener('lifeclip:auth-required', authRequired)
    }
  }, [])

  const signIn = useCallback(async (identifier: string, password: string) => {
    const current = await api.signIn(identifier, password)
    setUser(current)
    setStartupError('')
  }, [])

  const signUp = useCallback(async (username: string, email: string, password: string) => {
    const current = await api.signUp(username, email, password)
    setUser(current)
    setStartupError('')
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.signOut()
    } finally {
      resetSessionToken()
      setUser(null)
    }
  }, [])

  const clearUser = useCallback(() => {
    resetSessionToken()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    startupError,
    signIn,
    signUp,
    signOut,
    clearUser,
  }), [user, loading, startupError, signIn, signUp, signOut, clearUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
