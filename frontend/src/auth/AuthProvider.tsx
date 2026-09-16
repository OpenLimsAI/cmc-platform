import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '@/services/api'
import type { AuthStatus, QapIdentity } from '@/types/auth'
import {
  clearSession, getStoredToken, mdmLogout, startSessionGuard,
  TOKEN_CHANGED_EVENT, TOKEN_KEY, type LogoutReason,
} from '@/shared/cmabSession'

interface AuthContextValue {
  status: AuthStatus | null
  user: QapIdentity | null
  loading: boolean
  error: string | null
  errorStatus: number | null
  canRead: boolean
  canPreview: boolean
  reload: () => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [token, setToken] = useState(getStoredToken)
  const [generation, setGeneration] = useState(0)
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [user, setUser] = useState<QapIdentity | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const loadId = useRef(0)

  useEffect(() => {
    const syncToken = () => {
      // 核验期间关闭所有能力并隐藏内容。同一身份续期不丢失已选文件。
      setLoading(true)
      const nextToken = getStoredToken()
      setToken(nextToken)
      setGeneration((value) => value + 1)
      if (!nextToken) {
        setUser(null)
        navigate('/login', { replace: true })
      }
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key === TOKEN_KEY || event.key === null) syncToken()
    }
    window.addEventListener(TOKEN_CHANGED_EVENT, syncToken)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(TOKEN_CHANGED_EVENT, syncToken)
      window.removeEventListener('storage', onStorage)
    }
  }, [navigate])

  useEffect(() => {
    const id = ++loadId.current
    setLoading(true)
    setError(null)
    setErrorStatus(null)
    void (async () => {
      try {
        const current = (await api.authStatus()).data
        if (id !== loadId.current) return
        setStatus(current)
        if (current.configured && token) {
          const identity = (await api.me()).data
          if (id === loadId.current) setUser(identity)
        } else if (id === loadId.current) setUser(null)
      } catch (cause) {
        if (id !== loadId.current) return
        setUser(null)
        setError(cause instanceof Error ? cause.message : '身份状态读取失败')
        setErrorStatus(cause instanceof ApiError ? cause.status : null)
      } finally {
        if (id === loadId.current) setLoading(false)
      }
    })()
    return () => { loadId.current += 1 }
  }, [token, generation])

  const sessionEnded = useCallback((reason: LogoutReason) => {
    setUser(null)
    setLoading(true)
    const go = () => navigate(`/login?reason=${reason}`, { replace: true })
    if (reason === 'other-tab') {
      clearSession()
      go()
    } else {
      void mdmLogout().finally(go)
    }
  }, [navigate])

  useEffect(() => {
    if (!token || !status?.configured) return
    return startSessionGuard({ onLogout: sessionEnded })
  }, [Boolean(token), status?.configured, sessionEnded])

  const reload = useCallback(() => setGeneration((value) => value + 1), [])
  const logout = useCallback(async () => {
    // 立即隐藏受限页面；刷新 Cookie 的撤销交由 MDM。
    setUser(null)
    setLoading(true)
    await mdmLogout()
    navigate('/login', { replace: true })
  }, [navigate])

  const canRead = !loading && !error && Boolean(
    user ? user.can_read : status && !status.auth_required,
  )
  const canPreview = !loading && !error && status?.configured === true && user?.can_preview === true

  return (
    <AuthContext.Provider value={{ status, user, loading, error, errorStatus, canRead, canPreview, reload, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('AuthProvider 未挂载')
  return auth
}
