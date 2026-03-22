import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { linkRequest } from '@/api/me'
import type { LinkRequestResponse } from '@/api/types'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/hooks/useAuth'
import { isMiniApp } from '@/lib/telegram'

const POLL_INTERVAL_MS = 3000

export default function AccountPage() {
  const { user, logout, refresh } = useAuth()
  const navigate = useNavigate()

  const [linkData, setLinkData] = useState<LinkRequestResponse | null>(null)
  const [linking, setLinking] = useState(false)
  const [timeLeft, setTimeLeft] = useState(0)

  // Countdown timer for link code
  useEffect(() => {
    if (!linkData) return
    const expiresAt = new Date(linkData.expires_at).getTime()
    const update = () => {
      const left = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000))
      setTimeLeft(left)
      if (left === 0) setLinkData(null)
    }
    update()
    const t = setInterval(update, 1000)
    return () => clearInterval(t)
  }, [linkData])

  // Poll /api/me while link code is active to detect when linking completes
  useEffect(() => {
    if (!linkData || timeLeft <= 0) return

    const interval = setInterval(async () => {
      const me = await refresh()

      if (me === null) {
        // 401 — user was merged into Telegram account, JWT is now invalid
        clearInterval(interval)
        setLinkData(null)
        logout()
        navigate('/login')
        toast.info('Telegram привязан! Войдите снова с тем же email.')
        return
      }

      if (me.telegram_id !== null) {
        // Link completed successfully, user still has same JWT
        clearInterval(interval)
        setLinkData(null)
        toast.success('Telegram успешно привязан!')
      }
    }, POLL_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [linkData, timeLeft, refresh, logout, navigate])

  async function handleLinkRequest() {
    setLinking(true)
    try {
      const data = await linkRequest()
      setLinkData(data)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Ошибка')
    } finally {
      setLinking(false)
    }
  }

  if (!user) return null

  const displayName =
    user.display_name ?? user.first_name ?? user.username ?? user.email ?? 'Пользователь'

  const minutes = Math.floor(timeLeft / 60)
  const seconds = timeLeft % 60
  const timerLabel = `${minutes}:${String(seconds).padStart(2, '0')}`

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 bg-background border-b shadow-sm px-4 py-3 flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
          ← Назад
        </Button>
        <span className="font-semibold">Аккаунт</span>
      </header>

      <main className="max-w-2xl mx-auto p-4 space-y-4">
        {/* User info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Информация</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Имя</span>
              <span className="text-sm font-medium">{displayName}</span>
            </div>
            {user.email && (
              <>
                <Separator />
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <span className="text-sm text-muted-foreground shrink-0">Email</span>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-mono truncate">{user.email}</span>
                    <span className="shrink-0">
                      {user.email_verified
                        ? <Badge variant="secondary" className="text-xs">Подтверждён</Badge>
                        : <Badge variant="destructive" className="text-xs">Не подтверждён</Badge>
                      }
                    </span>
                  </div>
                </div>
              </>
            )}
            {user.telegram_id && (
              <>
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Telegram</span>
                  <div className="flex items-center gap-2">
                    {user.username
                      ? <span className="text-sm font-mono">@{user.username}</span>
                      : <span className="text-sm text-muted-foreground">ID: {user.telegram_id}</span>
                    }
                    <Badge variant="secondary" className="text-xs">Привязан</Badge>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Link Telegram section (only if not linked) */}
        {!user.telegram_id && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Привязать Telegram</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {linkData && timeLeft > 0 ? (
                <div className="space-y-3">
                  <Alert>
                    <AlertDescription className="space-y-2">
                      <p>Отправьте боту команду:</p>
                      <p className="font-mono text-lg font-bold text-center bg-muted rounded-lg py-2">
                        /link {linkData.code}
                      </p>
                      <p className="text-xs text-muted-foreground text-center">
                        Код действителен {timerLabel} · ожидание привязки...
                      </p>
                    </AlertDescription>
                  </Alert>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={handleLinkRequest}
                    disabled={linking}
                  >
                    Обновить код
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    Получите код и отправьте его боту командой <code>/link &lt;код&gt;</code>
                  </p>
                  <Button
                    className="w-full"
                    onClick={handleLinkRequest}
                    disabled={linking}
                  >
                    {linking ? 'Генерация кода...' : 'Получить код привязки'}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {!isMiniApp() && (
          <>
            <Separator />
            <Button
              variant="destructive"
              className="w-full"
              onClick={() => { logout(); navigate('/login') }}
            >
              Выйти из аккаунта
            </Button>
          </>
        )}
      </main>
    </div>
  )
}
