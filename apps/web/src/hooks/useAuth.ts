/**
 * useAuth — InsForge Auth hook.
 * Wraps the @insforge/sdk auth module for sign-in, sign-out,
 * and current user access.
 *
 * Phase 0: plumbing only. No UI screens yet.
 * Phase 1 will add sign-up flows, profile management, and protected routes.
 */
import { useState, useEffect } from 'react'
import { insforge } from '../services/insforgeClient'

export interface AuthUser {
  id: string
  email: string | null
}

export interface UseAuthReturn {
  user: AuthUser | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  getToken: () => Promise<string | null>
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    insforge.auth.getCurrentUser().then(({ data }) => {
      if (data?.user) {
        setUser({ id: data.user.id, email: data.user.email ?? null })
      }
      setLoading(false)
    })
  }, [])

  const signIn = async (email: string, password: string) => {
    const { data, error } = await insforge.auth.signInWithPassword({ email, password })
    if (error) throw new Error(error.message)
    if (data?.user) {
      setUser({ id: data.user.id, email: data.user.email ?? null })
    }
  }

  const signOut = async () => {
    await insforge.auth.signOut()
    setUser(null)
  }

  const getToken = async (): Promise<string | null> => {
    const { data } = await insforge.auth.getCurrentUser()
    // The session token lives on the returned session object
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (data as any)?.session?.access_token ?? null
  }

  return { user, loading, signIn, signOut, getToken }
}
