import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL: `${API_URL}/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// ---------------------------------------------------------------------------
// Auth interceptor
// ---------------------------------------------------------------------------
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ---------------------------------------------------------------------------
// Refresh-token logic — single in-flight, queue les requêtes pendantes, ne
// retry chaque requête qu'une seule fois (`_retry`), redirige sur /login si
// le refresh échoue.
// ---------------------------------------------------------------------------
type Queued = {
  resolve: (token: string) => void
  reject: (err: unknown) => void
}
let isRefreshing = false
let pending: Queued[] = []

function resolvePending(token: string | null, err?: unknown) {
  pending.forEach((p) => (token ? p.resolve(token) : p.reject(err)))
  pending = []
}

function clearAuthAndRedirect() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  // Si on est déjà sur /login on ne redirige pas pour éviter une boucle.
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    // Ne tente pas de refresh sur la route de refresh elle-même
    if (originalRequest.url?.includes('/auth/refresh')) {
      clearAuthAndRedirect()
      return Promise.reject(error)
    }

    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      clearAuthAndRedirect()
      return Promise.reject(error)
    }

    originalRequest._retry = true

    // Si un refresh est déjà en cours, on s'aligne dessus
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pending.push({
          resolve: (token) => {
            originalRequest.headers = originalRequest.headers ?? {}
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(client(originalRequest))
          },
          reject,
        })
      })
    }

    isRefreshing = true
    try {
      const res = await axios.post(`${API_URL}/v1/auth/refresh`, {
        refresh_token: refreshToken,
      }, { timeout: 15000 })
      const newAccess = res.data?.access_token as string | undefined
      const newRefresh = res.data?.refresh_token as string | undefined
      if (!newAccess || !newRefresh) throw new Error('Invalid refresh response')

      localStorage.setItem('access_token', newAccess)
      localStorage.setItem('refresh_token', newRefresh)
      resolvePending(newAccess)
      originalRequest.headers = originalRequest.headers ?? {}
      originalRequest.headers.Authorization = `Bearer ${newAccess}`
      return client(originalRequest)
    } catch (refreshErr) {
      resolvePending(null, refreshErr)
      clearAuthAndRedirect()
      return Promise.reject(refreshErr)
    } finally {
      isRefreshing = false
    }
  },
)

/**
 * Download a file using auth header instead of token in URL.
 */
export async function downloadWithAuth(url: string, filename: string): Promise<void> {
  const response = await client.get(url, { responseType: 'blob' })
  const blob = new Blob([response.data])
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

export default client
