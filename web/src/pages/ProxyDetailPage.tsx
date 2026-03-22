import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { deleteProxy, getProxies, getProxyStats } from '@/api/proxies'
import type { Proxy, ProxyStats } from '@/api/types'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'

export default function ProxyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const proxyId = Number(id)

  const [proxy, setProxy] = useState<Proxy | null>(null)
  const [stats, setStats] = useState<ProxyStats | null>(null)
  const [loadingProxy, setLoadingProxy] = useState(true)
  const [loadingStats, setLoadingStats] = useState(true)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    void loadProxy()
    void loadStats()
  }, [proxyId])

  async function loadProxy() {
    try {
      const all = await getProxies()
      const found = all.find((p) => p.id === proxyId)
      if (!found) {
        navigate('/')
        return
      }
      setProxy(found)
    } catch {
      navigate('/')
    } finally {
      setLoadingProxy(false)
    }
  }

  async function loadStats() {
    try {
      const data = await getProxyStats(proxyId)
      setStats(data)
    } catch {
      // stats unavailable
    } finally {
      setLoadingStats(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteProxy(proxyId)
      toast.success('Прокси удалён')
      navigate('/')
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Ошибка удаления')
      setDeleting(false)
    }
  }

  function copyToClipboard(text: string, label: string) {
    void navigator.clipboard.writeText(text)
    toast.success(`${label} скопирован`)
  }

  if (loadingProxy) {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-4 pt-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    )
  }

  if (!proxy) return null

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-4 py-3 flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
          ← Назад
        </Button>
        <span className="font-semibold">Прокси</span>
      </header>

      <main className="max-w-2xl mx-auto p-4 space-y-4">
        {/* Connection details */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Данные подключения</CardTitle>
              <Badge variant="secondary">MTProto</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Row label="Сервер" value={proxy.node.host} onCopy={() => copyToClipboard(proxy.node.host, 'Сервер')} />
            <Separator />
            <Row label="Порт" value={String(proxy.port)} onCopy={() => copyToClipboard(String(proxy.port), 'Порт')} />
            <Separator />
            <Row
              label="Секрет"
              value={proxy.secret}
              truncate
              onCopy={() => copyToClipboard(proxy.secret, 'Секрет')}
            />
            <Separator />
            <div className="pt-1">
              <Button
                className="w-full"
                onClick={() => copyToClipboard(proxy.tme_link, 'Ссылка')}
              >
                Копировать ссылку
              </Button>
              <a
                href={proxy.tme_link}
                className="mt-2 block text-center text-sm text-primary underline"
              >
                Открыть в Telegram
              </a>
            </div>
          </CardContent>
        </Card>

        {/* QR code */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">QR-код</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center py-2">
            <QRCodeSVG value={proxy.tme_link} size={200} />
          </CardContent>
        </Card>

        {/* Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Статистика</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingStats ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ) : stats ? (
              <div className="grid grid-cols-2 gap-3">
                <StatItem label="Соединений" value={stats.connections ?? '—'} />
                <StatItem label="Устройств (макс)" value={stats.max_devices ?? '—'} />
                <StatItem label="Трафик ↓" value={stats.traffic_rx ?? '—'} />
                <StatItem label="Трафик ↑" value={stats.traffic_tx ?? '—'} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Статистика недоступна</p>
            )}
          </CardContent>
        </Card>

        {/* Delete */}
        <Button
          variant="destructive"
          className="w-full"
          onClick={() => setShowDeleteDialog(true)}
        >
          Удалить прокси
        </Button>
      </main>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить прокси?</AlertDialogTitle>
            <AlertDialogDescription>
              Прокси {proxy.node.host}:{proxy.port} будет удалён. Это действие нельзя отменить.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? 'Удаление...' : 'Удалить'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function Row({
  label,
  value,
  truncate,
  onCopy,
}: {
  label: string
  value: string
  truncate?: boolean
  onCopy: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={`text-sm font-mono ${truncate ? 'truncate max-w-[220px]' : ''}`}>{value}</p>
      </div>
      <Button size="sm" variant="ghost" onClick={onCopy}>
        Копировать
      </Button>
    </div>
  )
}

function StatItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-muted rounded-lg p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold mt-1">{value}</p>
    </div>
  )
}
