import client from './client'

export async function getPlans() {
  const res = await client.get('/payments/plans')
  return res.data
}

export async function createCheckout(plan: string, currency = 'XOF') {
  const res = await client.post('/payments/checkout', { plan, currency })
  return res.data
}
