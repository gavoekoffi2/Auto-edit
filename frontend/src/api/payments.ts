import client from './client'

export interface PlanLimits {
  montages_per_month: number | null
  max_video_minutes: number | null
  concurrent_jobs: number | null
  clips_per_job: number
}

export interface PlanInfo {
  id: 'free' | 'pro' | 'enterprise'
  name: string
  price: { XOF: number; USD: number }
  limits: PlanLimits
}

export interface PlansResponse {
  period_days: number
  plans: PlanInfo[]
}

export interface PaymentStatus {
  id: string
  amount: number
  currency: string
  status: 'pending' | 'completed' | 'failed'
  plan: string
  created_at: string
  effective_plan: string
  subscription_expires_at: string | null
}

export async function getPlans(): Promise<PlansResponse> {
  const res = await client.get('/payments/plans')
  return res.data
}

export async function createCheckout(plan: string, currency = 'XOF'): Promise<{ payment_id: string; checkout_url: string }> {
  const res = await client.post('/payments/checkout', { plan, currency })
  return res.data
}

export async function verifyPayment(paymentId: string): Promise<PaymentStatus> {
  const res = await client.post(`/payments/${paymentId}/verify`)
  return res.data
}
