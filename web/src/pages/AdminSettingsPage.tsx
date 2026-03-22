import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getAdminSettings, updateBrandName, uploadLogo } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/hooks/useAuth'
import { useBranding } from '@/hooks/useBranding'

export default function AdminSettingsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { brandLogoUrl, refresh } = useBranding()

  const [brandName, setBrandName] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [loadingSettings, setLoadingSettings] = useState(true)

  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!user?.is_admin) {
      navigate('/', { replace: true })
      return
    }
    void loadSettings()
  }, [user, navigate])

  async function loadSettings() {
    try {
      const s = await getAdminSettings()
      setBrandName(s.brand_name ?? '')
    } catch {
      toast.error('Не удалось загрузить настройки')
    } finally {
      setLoadingSettings(false)
    }
  }

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault()
    setSavingName(true)
    try {
      await updateBrandName(brandName)
      await refresh()
      toast.success('Название обновлено')
    } catch {
      toast.error('Не удалось сохранить название')
    } finally {
      setSavingName(false)
    }
  }

  async function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingLogo(true)
    try {
      await uploadLogo(file)
      await refresh()
      toast.success('Логотип обновлён')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Ошибка загрузки логотипа')
    } finally {
      setUploadingLogo(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  if (loadingSettings) return null

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <div className="font-semibold text-lg">Настройки</div>
        <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
          ← Назад
        </Button>
      </header>

      <main className="max-w-xl mx-auto p-4 space-y-6">
        {/* Brand name */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Название сервиса</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSaveName} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="brand-name">Название</Label>
                <Input
                  id="brand-name"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  placeholder="MTG Proxy"
                  disabled={savingName}
                />
              </div>
              <Button type="submit" disabled={savingName || !brandName.trim()}>
                {savingName ? 'Сохранение...' : 'Сохранить'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Separator />

        {/* Logo */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Логотип</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {brandLogoUrl && (
              <div className="flex items-center gap-3">
                <img
                  src={brandLogoUrl}
                  alt="Текущий логотип"
                  className="h-16 w-16 object-contain border rounded-lg p-1"
                />
                <span className="text-sm text-muted-foreground">Текущий логотип</span>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="logo-upload">Загрузить новый логотип</Label>
              <p className="text-xs text-muted-foreground">
                PNG, JPEG, SVG, WebP или GIF — не более 2 МБ
              </p>
              <input
                ref={fileInputRef}
                id="logo-upload"
                type="file"
                accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif"
                className="hidden"
                onChange={handleLogoChange}
                disabled={uploadingLogo}
              />
              <Button
                type="button"
                variant="outline"
                disabled={uploadingLogo}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploadingLogo ? 'Загрузка...' : 'Выбрать файл'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
