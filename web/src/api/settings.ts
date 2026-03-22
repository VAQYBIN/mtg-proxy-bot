import type { AdminSettings, PublicSettings } from './types'

export async function getPublicSettings(): Promise<PublicSettings> {
  const res = await fetch('/api/settings')
  if (!res.ok) throw new Error('Failed to load settings')
  return res.json() as Promise<PublicSettings>
}

export async function getAdminSettings(): Promise<AdminSettings> {
  const token = localStorage.getItem('jwt')
  const res = await fetch('/api/admin/settings', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to load admin settings')
  return res.json() as Promise<AdminSettings>
}

export async function updateBrandName(brandName: string): Promise<AdminSettings> {
  const token = localStorage.getItem('jwt')
  const res = await fetch('/api/admin/settings', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ brand_name: brandName }),
  })
  if (!res.ok) throw new Error('Failed to update settings')
  return res.json() as Promise<AdminSettings>
}

export async function uploadLogo(file: File): Promise<{ url: string }> {
  const token = localStorage.getItem('jwt')
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/admin/settings/logo', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error((err as { detail?: string }).detail ?? 'Upload failed')
  }
  return res.json() as Promise<{ url: string }>
}
