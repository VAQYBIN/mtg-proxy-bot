import { createContext, useContext, useEffect, useState } from 'react'
import { getPublicSettings } from '@/api/settings'

interface BrandingContextValue {
  brandName: string
  brandLogoUrl: string
  refresh: () => Promise<void>
}

const DEFAULT_BRAND = 'MTG Proxy'

const BrandingContext = createContext<BrandingContextValue>({
  brandName: DEFAULT_BRAND,
  brandLogoUrl: '',
  refresh: async () => {},
})

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [brandName, setBrandName] = useState(DEFAULT_BRAND)
  const [brandLogoUrl, setBrandLogoUrl] = useState('')

  async function load() {
    try {
      const s = await getPublicSettings()
      const name = s.brand_name || DEFAULT_BRAND
      setBrandName(name)
      setBrandLogoUrl(s.brand_logo_url || '')
      document.title = name
    } catch {
      // Используем дефолты при ошибке сети
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <BrandingContext.Provider value={{ brandName, brandLogoUrl, refresh: load }}>
      {children}
    </BrandingContext.Provider>
  )
}

export function useBranding() {
  return useContext(BrandingContext)
}
