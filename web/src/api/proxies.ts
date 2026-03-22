import { api } from './client'
import type { Node, Proxy, ProxyStats } from './types'

export function getNodes() {
  return api.get<Node[]>('/api/nodes')
}

export function getProxies() {
  return api.get<Proxy[]>('/api/proxies')
}

export function createProxy(nodeId: number) {
  return api.post<Proxy>('/api/proxies', { node_id: nodeId })
}

export function deleteProxy(proxyId: number) {
  return api.delete<void>(`/api/proxies/${proxyId}`)
}

export function getProxyStats(proxyId: number) {
  return api.get<ProxyStats>(`/api/proxies/${proxyId}/stats`)
}
