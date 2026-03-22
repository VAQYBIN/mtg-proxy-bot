import { createContext, useContext, useEffect, useState } from 'react'
import { getPublicSettings } from '@/api/settings'

interface BrandingContextValue {
  brandName: string
  brandLogoUrl: string
  adEnabled: boolean
  adUrl: string
  adText: string
  adButtonText: string
  refresh: () => Promise<void>
}

const DEFAULT_BRAND = 'MTG Proxy'

const BrandingContext = createContext<BrandingContextValue>({
  brandName: DEFAULT_BRAND,
  brandLogoUrl: '',
  adEnabled: false,
  adUrl: '',
  adText: '',
  adButtonText: 'Подробнее',
  refresh: async () => {},
})

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [brandName, setBrandName] = useState(DEFAULT_BRAND)
  const [brandLogoUrl, setBrandLogoUrl] = useState('')
  const [adEnabled, setAdEnabled] = useState(false)
  const [adUrl, setAdUrl] = useState('')
  const [adText, setAdText] = useState('')
  const [adButtonText, setAdButtonText] = useState('Подробнее')

  async function load() {
    try {
      const s = await getPublicSettings()
      const name = s.brand_name || DEFAULT_BRAND
      setBrandName(name)
      setBrandLogoUrl(s.brand_logo_url || '')
      setAdEnabled(s.ad_enabled)
      setAdUrl(s.ad_url || '')
      setAdText(s.ad_text || '')
      setAdButtonText(s.ad_button_text || 'Подробнее')
      document.title = name
    } catch {
      // Используем дефолты при ошибке сети
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <BrandingContext.Provider
      value={{ brandName, brandLogoUrl, adEnabled, adUrl, adText, adButtonText, refresh: load }}
    >
      {children}
    </BrandingContext.Provider>
  )
}

export function useBranding() {
  return useContext(BrandingContext)
}
