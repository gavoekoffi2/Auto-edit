import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '../store/authStore'

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
export type AutoEditRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean
  _skipAuthRetry?: boolean
}
let isRefreshing = false
let pending: Queued[] = []

function resolvePending(token: string | null, err?: unknown) {
  pending.forEach((p) => (token ? p.resolve(token) : p.reject(err)))
  pending = []
}

function clearAuthAndRedirect() {
  // Vide aussi le store: sinon la navbar affiche encore « connecté ».
  useAuthStore.getState().logout()
  // Si on est déjà sur /login on ne redirige pas pour éviter une boucle.
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

export async function refreshAuthTokens(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('Session expirée. Connecte-toi puis relance l’upload.')

  const res = await axios.post(`${API_URL}/v1/auth/refresh`, {
    refresh_token: refreshToken,
  }, { timeout: 15000 })
  const newAccess = res.data?.access_token as string | undefined
  const newRefresh = res.data?.refresh_token as string | undefined
  if (!newAccess || !newRefresh) throw new Error('Session expirée. Connecte-toi puis relance l’upload.')

  // Store + localStorage synchronisés (les URL de stream lisent le jeton courant).
  useAuthStore.getState().setTokens(newAccess, newRefresh)
  return newAccess
}

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AutoEditRequestConfig
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry || originalRequest._skipAuthRetry) {
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
      const newAccess = await refreshAuthTokens()
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
 * Download a file using the auth header instead of exposing the token in the URL.
 *
 * Rendered videos can be large (tens or hundreds of MB). Keep this request out
 * of the default 30s axios timeout, otherwise mobile/slow connections receive
 * a generic "download failed" even though the backend is correctly streaming a
 * completed montage. Also keep the object URL alive briefly: revoking it
 * immediately after `click()` is unreliable on some mobile browsers.
 */
export async function downloadWithAuth(url: string, filename: string): Promise<void> {
  const response = await client.get(url, {
    responseType: 'blob',
    timeout: 0,
  })

  const rawContentType = response.headers['content-type']
  const contentType = typeof rawContentType === 'string' ? rawContentType : 'video/mp4'
  const blob = new Blob([response.data], { type: contentType })
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

/**
 * Message lisible pour n'importe quelle erreur d'API.
 *
 * FastAPI renvoie `detail` sous trois formes: une chaîne, une liste d'erreurs
 * de validation (422) ou un objet `{code, message}` (erreurs produit). Rendre
 * directement un objet/une liste dans un toast faisait planter React.
 */
export function getErrorMessage(err: unknown, fallback = 'Une erreur est survenue. Réessaie.'): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response
    const detail = res?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
        .filter(Boolean)
        .map((m) => m.replace(/^Value error, /, ''))
      if (msgs.length) return msgs.join('. ')
    }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as { message: unknown }).message)
    }
    if (res?.status === 429) return 'Trop de tentatives. Patiente un peu puis réessaie.'
    if (res?.status && res.status >= 500) return 'Le serveur rencontre un problème. Réessaie dans un instant.'
  }
  if (err && typeof err === 'object' && 'code' in err && (err as { code?: string }).code === 'ERR_NETWORK') {
    return 'Connexion impossible. Vérifie ta connexion internet.'
  }
  if (err instanceof Error && err.message && !/^Request failed with status code/.test(err.message)) {
    return err.message
  }
  return fallback
}

export default client
