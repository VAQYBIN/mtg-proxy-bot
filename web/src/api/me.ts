import { api } from './client'
import type { LinkRequestResponse, User } from './types'

export function getMe() {
  return api.get<User>('/api/me')
}

export function linkRequest() {
  return api.post<LinkRequestResponse>('/api/me/link/request')
}
