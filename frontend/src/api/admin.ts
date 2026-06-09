import client from './client'

export interface AdminUser {
  id: string
  email: string
  full_name: string | null
  plan: string
  effective_plan: string
  subscription_expires_at: string | null
  is_admin: boolean
  is_active: boolean
  created_at: string
  videos_count: number
}

export interface GrantSubscriptionPayload {
  email: string
  plan: 'free' | 'pro' | 'enterprise'
  duration_days: number | null
  create_if_missing?: boolean
  initial_password?: string | null
  full_name?: string | null
  is_admin?: boolean | null
  is_active?: boolean | null
}

export interface GrantSubscriptionResult {
  user: AdminUser
  message: string
  account_created: boolean
  temporary_password: string | null
}

export async function listAdminUsers(q?: string): Promise<AdminUser[]> {
  const response = await client.get('/admin/users', { params: { q: q || undefined } })
  return response.data
}

export async function grantSubscription(payload: GrantSubscriptionPayload): Promise<GrantSubscriptionResult> {
  const response = await client.post('/admin/subscriptions/grant', payload)
  return response.data
}
