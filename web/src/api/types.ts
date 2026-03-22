export interface User {
  id: number
  telegram_id: number | null
  username: string | null
  first_name: string | null
  display_name: string | null
  email: string | null
  email_verified: boolean
  is_banned: boolean
  is_admin: boolean
  created_at: string
}

export interface PublicSettings {
  brand_name: string
  brand_logo_url: string
}

export interface AdminSettings {
  brand_name: string
  brand_logo_url: string
}

export interface Node {
  id: number
  name: string
  flag: string | null
  host: string
}

export interface Proxy {
  id: number
  node: Node
  link: string
  port: number
  secret: string
  expires_at: string | null
  traffic_limit_gb: number | null
  is_active: boolean
  created_at: string
  tme_link: string
}

export interface ProxyStats {
  connections: number | null
  max_devices: number | null
  traffic_rx: string | null
  traffic_tx: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface LinkRequestResponse {
  code: string
  expires_at: string
}
