import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { telegramMiniAppAuth } from '@/api/auth'
import { getMe } from '@/api/me'
import type { User } from '@/api/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (token: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<User | null>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    // Если открыто внутри Telegram Mini App — авто-авторизация через initData.
    // Это перезаписывает JWT при каждом открытии, гарантируя свежий токен.
    const tgWebApp = window.Telegram?.WebApp
    if (tgWebApp?.initData) {
      tgWebApp.ready()
      tgWebApp.expand()
      try {
        const { access_token } = await telegramMiniAppAuth(tgWebApp.initData)
        localStorage.setItem('jwt', access_token)
      } catch {
        // initData невалидна (например, открыто в браузере с mock) — идём дальше
      }
    }

    const token = localStorage.getItem('jwt')
    if (!token) {
      setLoading(false)
      return
    }
    try {
      const me = await getMe()
      setUser(me)
    } catch {
      localStorage.removeItem('jwt')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadUser()
  }, [loadUser])

  const login = useCallback(async (token: string) => {
    localStorage.setItem('jwt', token)
    const me = await getMe()
    setUser(me)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('jwt')
    setUser(null)
  }, [])

  const refresh = useCallback(async (): Promise<User | null> => {
    try {
      const me = await getMe()
      setUser(me)
      return me
    } catch {
      return null
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
