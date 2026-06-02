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

export async function logoutApi() {
  const refresh_token = localStorage.getItem('refresh_token')
  if (!refresh_token) return
  try {
    await client.post('/auth/logout', { refresh_token })
  } catch {
    /* best-effort: on nettoie le client meme si le serveur ne repond pas */
  }
}

export async function requestPasswordReset(email: string) {
  const res = await client.post('/auth/password-reset/request', { email })
  return res.data
}

export async function confirmPasswordReset(token: string, new_password: string) {
  const res = await client.post('/auth/password-reset/confirm', {
    token,
    new_password,
  })
  return res.data
}
