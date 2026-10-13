/**
 * AuthContext — app-wide auth state using InsForge SDK.
 * Handles: sign-up (with code verification), sign-in, sign-out, OAuth,
 * and persistent session storage in localStorage across page reloads.
 */
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from 'react'
import { insforge } from '../../services/insforgeClient'

export interface AuthUser {
  id: string
  email: string | null
  name: string | null
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  token: string | null
  signUp: (email: string, password: string, name?: string) => Promise<{ requiresVerification: boolean }>
  verifyEmail: (email: string, otp: string) => Promise<void>
  resendVerification: (email: string) => Promise<void>
  signIn: (email: string, password: string) => Promise<void>
  signInWithOAuth: (provider: 'google' | 'github') => Promise<void>
  signOut: () => Promise<void>
  refreshToken: () => Promise<string | null>
}

const STORAGE_KEY = 'cricket_auth_session'

function saveStoredSession(user: AuthUser, token: string) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ user, token }))
  } catch {
    // ignore storage errors
  }
}

function isJwtExpired(token: string): boolean {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return true
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
    if (typeof payload.exp === 'number') {
      return payload.exp * 1000 < Date.now() + 5000
    }
    return false
  } catch {
    return true
  }
}

function loadStoredSession(): { user: AuthUser; token: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed?.user?.id && parsed?.token) {
      if (isJwtExpired(parsed.token)) {
        localStorage.removeItem(STORAGE_KEY)
        return null
      }
      return parsed
    }
  } catch {
    // ignore parse errors
  }
  return null
}

function clearStoredSession() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const cancelled = useRef(false)

  useEffect(() => {
    const handleUnauthorized = () => {
      clearStoredSession()
      setUser(null)
      setToken(null)
    }
    window.addEventListener('cricket:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('cricket:unauthorized', handleUnauthorized)
  }, [])

  useEffect(() => {
    cancelled.current = false
    async function hydrate() {
      try {
        // 1. Restore valid non-expired session from localStorage if available
        const stored = loadStoredSession()
        if (stored && !cancelled.current) {
          setUser(stored.user)
          setToken(stored.token)
        }

        // 2. Also check SDK session / refresh if available
        const { data } = await insforge.auth.getCurrentUser()
        if (cancelled.current) return
        if (data?.user) {
          const hydratedUser: AuthUser = {
            id: data.user.id,
            email: data.user.email ?? null,
            name: ((data.user as Record<string, unknown>).name as string) ?? null,
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const sdkToken = (data as any)?.accessToken ?? (data as any)?.session?.access_token ?? stored?.token ?? null
          if (sdkToken && !isJwtExpired(sdkToken)) {
            setUser(hydratedUser)
            setToken(sdkToken)
            saveStoredSession(hydratedUser, sdkToken)
          }
        }
      } catch {
        // keep stored session if valid, or remain unauthenticated
      } finally {
        if (!cancelled.current) setLoading(false)
      }
    }
    void hydrate()
    return () => { cancelled.current = true }
  }, [])

  const signUp: AuthContextValue['signUp'] = async (email, password, name) => {
    const { data, error } = await insforge.auth.signUp({
      email,
      password,
      name,
      redirectTo: `${window.location.origin}/sign-in`,
    })
    if (error) throw new Error(error.message)
    // If email verification is not required and token was returned immediately
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const immediateToken = (data as any)?.accessToken ?? (data as any)?.session?.access_token ?? null
    if (data?.user && immediateToken) {
      const u: AuthUser = { id: data.user.id, email: data.user.email ?? null, name: name ?? null }
      setUser(u)
      setToken(immediateToken)
      saveStoredSession(u, immediateToken)
    }
    return { requiresVerification: !!data?.requireEmailVerification }
  }

  const verifyEmail: AuthContextValue['verifyEmail'] = async (email, otp) => {
    const { data, error } = await insforge.auth.verifyEmail({ email, otp })
    if (error) throw new Error(error.message)
    if (data?.user) {
      const u: AuthUser = { id: data.user.id, email: data.user.email ?? null, name: null }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const accessToken = (data as any)?.accessToken ?? (data as any)?.session?.access_token ?? null
      setUser(u)
      setToken(accessToken)
      if (accessToken) saveStoredSession(u, accessToken)
    }
  }

  const resendVerification: AuthContextValue['resendVerification'] = async (email) => {
    const { error } = await insforge.auth.resendVerificationEmail({
      email,
      redirectTo: `${window.location.origin}/sign-in`,
    })
    if (error) throw new Error(error.message)
  }

  const signIn: AuthContextValue['signIn'] = async (email, password) => {
    const { data, error } = await insforge.auth.signInWithPassword({ email, password })
    if (error) {
      if (error.statusCode === 403) throw new Error('Email not verified. Please check your inbox.')
      throw new Error(error.message)
    }
    if (data?.user) {
      const u: AuthUser = {
        id: data.user.id,
        email: data.user.email ?? null,
        name: ((data.user as Record<string, unknown>).name as string) ?? null,
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const accessToken = (data as any)?.accessToken ?? (data as any)?.session?.access_token ?? null
      setUser(u)
      setToken(accessToken)
      if (accessToken) {
        saveStoredSession(u, accessToken)
      }
    }
  }

  const signInWithOAuth: AuthContextValue['signInWithOAuth'] = async (provider) => {
    await insforge.auth.signInWithOAuth(provider, {
      redirectTo: `${window.location.origin}/dashboard`,
    })
  }

  const signOut: AuthContextValue['signOut'] = async () => {
    try {
      await insforge.auth.signOut()
    } catch {
      // ignore signOut network errors
    }
    clearStoredSession()
    setUser(null)
    setToken(null)
  }

  const refreshToken: AuthContextValue['refreshToken'] = async () => {
    try {
      const { data } = await insforge.auth.refreshSession()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const t = (data as any)?.accessToken ?? (data as any)?.session?.access_token ?? token
      if (t) {
        setToken(t)
        if (user) saveStoredSession(user, t)
      }
      return t
    } catch {
      return token
    }
  }

  return (
    <AuthContext.Provider value={{
      user, loading, token,
      signUp, verifyEmail, resendVerification,
      signIn, signInWithOAuth, signOut, refreshToken,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
