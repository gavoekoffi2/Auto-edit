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
  jobs_count: number
  completed_jobs_count: number
  failed_jobs_count: number
  total_spent_xof: number
  last_activity_at: string | null
}

export interface AdminStats {
  users_total: number
  active_users: number
  blocked_users: number
  admins: number
  free_users: number
  pro_users: number
  enterprise_users: number
  videos_total: number
  jobs_total: number
  completed_jobs: number
  failed_jobs: number
  pending_jobs: number
  processing_jobs: number
  revenue_xof: number
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

export async function getAdminStats(): Promise<AdminStats> {
  const response = await client.get('/admin/stats')
  return response.data
}

export async function listAdminUsers(q?: string): Promise<AdminUser[]> {
  const response = await client.get('/admin/users', { params: { q: q || undefined, limit: 200 } })
  return response.data
}

export async function grantSubscription(payload: GrantSubscriptionPayload): Promise<GrantSubscriptionResult> {
  const response = await client.post('/admin/subscriptions/grant', payload)
  return response.data
}

export async function activateUser(userId: string): Promise<AdminUser> {
  const response = await client.post(`/admin/users/${userId}/activate`)
  return response.data
}

export async function deactivateUser(userId: string): Promise<AdminUser> {
  const response = await client.post(`/admin/users/${userId}/deactivate`)
  return response.data
}

export async function deleteUser(userId: string): Promise<void> {
  await client.delete(`/admin/users/${userId}`)
}
