import client from './client'

export interface PlanDescriptor {
  id: 'free' | 'pro' | 'enterprise'
  name: string
  price: { XOF: number; USD: number }
  features: string[]
}

export interface PlansResponse {
  plans: PlanDescriptor[]
  payments_enabled?: boolean
  subscription_days?: number
}

export interface PaymentStatus {
  id: string
  amount: number
  currency: string
  status: 'pending' | 'completed' | 'failed'
  plan: string
  created_at: string
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
