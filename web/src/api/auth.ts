import { api } from './client'
import type { TokenResponse } from './types'

export function emailRegister(email: string) {
  return api.post<{ detail: string }>('/auth/email/register', { email })
}

export function emailVerify(email: string, code: string) {
  return api.post<TokenResponse>('/auth/email/verify', { email, code })
}

export function emailResend(email: string) {
  return api.post<{ detail: string }>('/auth/email/resend', { email })
}

export interface TelegramWidgetData {
  id: number
  first_name: string
  auth_date: number
  hash: string
  username?: string
  last_name?: string
  photo_url?: string
}

export function telegramWidgetAuth(data: TelegramWidgetData) {
  return api.post<TokenResponse>('/auth/telegram/widget', data)
}

export function telegramMiniAppAuth(initData: string) {
  return api.post<TokenResponse>('/auth/telegram/miniapp', { init_data: initData })
}
