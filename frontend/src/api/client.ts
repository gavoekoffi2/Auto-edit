import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL: `${API_URL}/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30s timeout
})

// Add auth token to requests
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Shared in-flight refresh promise so concurrent 401s trigger only ONE refresh
// request. Without this, N simultaneous failed requests would fire N refreshes,
// racing each other and potentially invalidating the rotated refresh token.
let refreshPromise: Promise<string | null> | null = null

function performRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) return Promise.resolve(null)
    refreshPromise = axios
      .post(`${API_URL}/v1/auth/refresh`, { refresh_token: refreshToken })
      .then((res) => {
        if (res.data?.access_token && res.data?.refresh_token) {
          localStorage.setItem('access_token', res.data.access_token)
          localStorage.setItem('refresh_token', res.data.refresh_token)
          return res.data.access_token as string
        }
        return null
      })
      .catch(() => null)
      .finally(() => {
        // Allow a fresh refresh attempt once this one settles.
        refreshPromise = null
      })
  }
  return refreshPromise
}

// Handle 401 responses with a single, de-duplicated token refresh.
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true
      const newToken = await performRefresh()
      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return client(originalRequest)
      }
      // Refresh failed → sync Zustand store + localStorage, then redirect.
      const { useAuthStore } = await import('../store/authStore')
      useAuthStore.getState().logout()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
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
