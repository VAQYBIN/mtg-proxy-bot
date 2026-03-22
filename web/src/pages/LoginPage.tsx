import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { emailRegister, emailResend, emailVerify, type TelegramWidgetData, telegramWidgetAuth } from '@/api/auth'
import { ApiError } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/hooks/useAuth'
import { useBranding } from '@/hooks/useBranding'

type Step = 'email' | 'otp'

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramWidgetData) => void
  }
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const { brandName, brandLogoUrl } = useBranding()

  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [step, setStep] = useState<Step>('email')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resendCooldown, setResendCooldown] = useState(0)

  const tgWidgetRef = useRef<HTMLDivElement>(null)

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown <= 0) return
    const t = setInterval(() => setResendCooldown((v) => v - 1), 1000)
    return () => clearInterval(t)
  }, [resendCooldown])

  // Telegram Login Widget
  useEffect(() => {
    const botUsername = import.meta.env.VITE_BOT_USERNAME as string | undefined
    if (!botUsername || !tgWidgetRef.current) return

    window.onTelegramAuth = async (data) => {
      setLoading(true)
      setError('')
      try {
        const { access_token } = await telegramWidgetAuth(data)
        await login(access_token)
        navigate('/')
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Ошибка авторизации')
      } finally {
        setLoading(false)
      }
    }

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', 'onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    tgWidgetRef.current.appendChild(script)

    return () => {
      delete window.onTelegramAuth
    }
  }, [login, navigate])

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    setError('')
    try {
      await emailRegister(email)
      setStep('otp')
      setResendCooldown(60)
      toast.success('Код отправлен на ' + email)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Ошибка отправки')
    } finally {
      setLoading(false)
    }
  }

  async function handleOtpComplete(value: string) {
    if (value.length < 6) return
    setLoading(true)
    setError('')
    try {
      const { access_token } = await emailVerify(email, value)
      await login(access_token)
      navigate('/')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Неверный код')
      setOtp('')
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    if (resendCooldown > 0) return
    setLoading(true)
    try {
      await emailResend(email)
      setResendCooldown(60)
      toast.success('Новый код отправлен')
    } catch {
      toast.error('Не удалось отправить код')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl flex items-center justify-center gap-2">
            {brandLogoUrl && (
              <img src={brandLogoUrl} alt="" className="h-8 w-8 object-contain" />
            )}
            {brandName}
          </CardTitle>
          <CardDescription>Войдите, чтобы управлять прокси</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="email">
            <TabsList className="w-full mb-6">
              <TabsTrigger value="email" className="flex-1">Email</TabsTrigger>
              <TabsTrigger value="telegram" className="flex-1">Telegram</TabsTrigger>
            </TabsList>

            <TabsContent value="email">
              {step === 'email' ? (
                <form onSubmit={handleEmailSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={loading}
                      autoFocus
                    />
                  </div>
                  {error && (
                    <Alert variant="destructive">
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                  <Button type="submit" className="w-full" disabled={loading || !email}>
                    {loading ? 'Отправка...' : 'Получить код'}
                  </Button>
                </form>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground text-center">
                    Введите 6-значный код, отправленный на <strong>{email}</strong>
                  </p>
                  <div className="flex justify-center">
                    <InputOTP
                      maxLength={6}
                      value={otp}
                      onChange={setOtp}
                      onComplete={handleOtpComplete}
                      disabled={loading}
                    >
                      <InputOTPGroup>
                        <InputOTPSlot index={0} />
                        <InputOTPSlot index={1} />
                        <InputOTPSlot index={2} />
                        <InputOTPSlot index={3} />
                        <InputOTPSlot index={4} />
                        <InputOTPSlot index={5} />
                      </InputOTPGroup>
                    </InputOTP>
                  </div>
                  {error && (
                    <Alert variant="destructive">
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => { setStep('email'); setError(''); setOtp('') }}
                    >
                      Назад
                    </Button>
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={handleResend}
                      disabled={loading || resendCooldown > 0}
                    >
                      {resendCooldown > 0 ? `Повторить (${resendCooldown}с)` : 'Отправить снова'}
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="telegram">
              <div className="space-y-4">
                {import.meta.env.VITE_BOT_USERNAME ? (
                  <div className="flex justify-center py-4">
                    <div ref={tgWidgetRef} />
                  </div>
                ) : (
                  <Alert>
                    <AlertDescription>
                      Войти через Telegram можно через Mini App внутри бота.
                    </AlertDescription>
                  </Alert>
                )}
                {error && (
                  <Alert variant="destructive">
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
