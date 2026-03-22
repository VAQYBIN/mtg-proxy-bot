interface TelegramWebApp {
  initData: string
  initDataUnsafe: {
    user?: {
      id: number
      first_name: string
      last_name?: string
      username?: string
      language_code?: string
    }
    query_id?: string
    auth_date: number
    hash: string
  }
  ready(): void
  expand(): void
  close(): void
  platform: string
  colorScheme: 'light' | 'dark'
  isExpanded: boolean
  viewportHeight: number
  viewportStableHeight: number
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp
  }
}
