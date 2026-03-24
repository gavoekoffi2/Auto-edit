import client from './client'

export async function login(email: string, password: string) {
  const res = await client.post('/auth/login', { email, password })
  return res.data
}

export async function signup(email: string, password: string, full_name?: string) {
  const res = await client.post('/auth/signup', { email, password, full_name })
  return res.data
}

export async function getMe() {
  const res = await client.get('/auth/me')
  return res.data
}
