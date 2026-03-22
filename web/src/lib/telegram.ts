export const isMiniApp = (): boolean =>
  typeof window !== 'undefined' && !!window.Telegram?.WebApp?.initData
