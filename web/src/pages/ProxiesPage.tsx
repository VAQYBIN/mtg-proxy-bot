import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { createProxy, getNodes, getProxies } from '@/api/proxies'
import type { Node, Proxy } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/hooks/useAuth'
import { isMiniApp } from '@/lib/telegram'

export default function ProxiesPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [proxies, setProxies] = useState<Proxy[]>([])
  const [nodes, setNodes] = useState<Node[]>([])
  const [loadingProxies, setLoadingProxies] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [creating, setCreating] = useState(false)
  const [selectedNode, setSelectedNode] = useState<number | null>(null)

  useEffect(() => {
    void loadProxies()
    void loadNodes()
  }, [])

  async function loadProxies() {
    try {
      const data = await getProxies()
      setProxies(data)
    } catch {
      toast.error('Не удалось загрузить прокси')
    } finally {
      setLoadingProxies(false)
    }
  }

  async function loadNodes() {
    try {
      const data = await getNodes()
      setNodes(data)
    } catch {
      // nodes might be unavailable
    }
  }

  function openCreateDialog() {
    if (nodes.length === 1) {
      setSelectedNode(nodes[0].id)
    }
    setShowCreateDialog(true)
  }

  async function handleCreate() {
    const nodeId = selectedNode ?? nodes[0]?.id
    if (!nodeId) return
    setCreating(true)
    try {
      const proxy = await createProxy(nodeId)
      setProxies((prev) => [...prev, proxy])
      setShowCreateDialog(false)
      toast.success('Прокси создан')
      navigate(`/proxy/${proxy.id}`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Ошибка создания прокси')
    } finally {
      setCreating(false)
    }
  }

  function copyLink(tmeLink: string) {
    void navigator.clipboard.writeText(tmeLink)
    toast.success('Ссылка скопирована')
  }

  const displayName =
    user?.display_name ?? user?.first_name ?? user?.username ?? user?.email ?? 'Пользователь'

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <div className="font-semibold text-lg">MTG Proxy</div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/account')}>
            {displayName}
          </Button>
          {!isMiniApp() && (
            <Button variant="outline" size="sm" onClick={logout}>
              Выйти
            </Button>
          )}
        </div>
      </header>

      <main className="max-w-2xl mx-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Мои прокси</h1>
          <Button onClick={openCreateDialog} disabled={nodes.length === 0}>
            + Создать прокси
          </Button>
        </div>

        <Separator />

        {loadingProxies ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        ) : proxies.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <p className="text-lg">У вас пока нет прокси</p>
            <p className="text-sm mt-1">Нажмите «Создать прокси», чтобы начать</p>
          </div>
        ) : (
          <div className="space-y-3">
            {proxies.map((proxy) => (
              <Card
                key={proxy.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => navigate(`/proxy/${proxy.id}`)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-mono">
                      {proxy.node.host}:{proxy.port}
                    </CardTitle>
                    <Badge variant="secondary">MTProto</Badge>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground font-mono truncate max-w-[60%]">
                      {proxy.secret.slice(0, 20)}…
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => { e.stopPropagation(); copyLink(proxy.tme_link) }}
                    >
                      Копировать
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>

      {/* Create proxy dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Создать прокси</DialogTitle>
            <DialogDescription>
              Выберите сервер для нового MTProto прокси
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            {nodes.map((node) => (
              <button
                key={node.id}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                  selectedNode === node.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
                onClick={() => setSelectedNode(node.id)}
              >
                <div className="font-medium">{node.name ?? node.host}</div>
                <div className="text-xs text-muted-foreground">{node.host}</div>
              </button>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Отмена
            </Button>
            <Button
              onClick={handleCreate}
              disabled={creating || (nodes.length > 1 && selectedNode === null)}
            >
              {creating ? 'Создание...' : 'Создать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
