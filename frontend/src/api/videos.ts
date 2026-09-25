import client, { refreshAuthTokens } from './client'

export const MAX_FILE_SIZE_MB = 5120
export const ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'mov', 'm4v', 'avi', 'mkv', 'webm', 'flv', 'wmv', '3gp', '3g2', 'mts', 'm2ts']
export const ALLOWED_VIDEO_MIME_TYPES = [
  'video/mp4',
  'video/quicktime',
  'video/x-m4v',
  'video/x-msvideo',
  'video/x-matroska',
  'video/webm',
  'video/x-flv',
  'video/x-ms-wmv',
  'video/3gpp',
  'video/3gpp2',
  'video/mp2t',
]

function isAllowedVideo(file: File) {
  const extension = file.name.split('.').pop()?.toLowerCase()
  return (
    (file.type && ALLOWED_VIDEO_MIME_TYPES.includes(file.type)) ||
    (extension ? ALLOWED_VIDEO_EXTENSIONS.includes(extension) : false)
  )
}

export function validateVideoFile(file: File) {
  const maxBytes = MAX_FILE_SIZE_MB * 1024 * 1024
  if (file.size > maxBytes) {
    throw new Error(`Fichier trop lourd. Maximum: ${MAX_FILE_SIZE_MB}MB.`)
  }

  if (!isAllowedVideo(file)) {
    throw new Error(`Format vidéo non supporté. Formats acceptés: ${ALLOWED_VIDEO_EXTENSIONS.map((ext) => ext.toUpperCase()).join(', ')}.`)
  }
}

async function warmAuthSession() {
  // Force le refresh token AVANT d'envoyer une grosse vidéo. Sinon un token
  // expiré peut n'être découvert qu'après plusieurs minutes d'upload mobile,
  // et Axios relançait le POST après 401: la barre revenait de 99% à 0%.
  await refreshAuthTokens()
}

export interface UploadCheck {
  can_upload: boolean
  reason: string | null
  monthly_used: number
  monthly_limit: number | null
  max_duration_s: number | null
  max_upload_mb: number
}

export type UploadPurpose = 'edit' | 'clips'

export async function getUploadCheck(purpose: UploadPurpose = 'edit'): Promise<UploadCheck> {
  const res = await client.get(`/videos/upload-check?purpose=${purpose}`, { timeout: 15000 })
  return res.data
}

/** Durée de la vidéo lue localement (métadonnées), sans rien envoyer. */
export function probeLocalDuration(file: File, timeoutMs = 8000): Promise<number | null> {
  return new Promise((resolve) => {
    let settled = false
    const url = URL.createObjectURL(file)
    const el = document.createElement('video')
    const done = (value: number | null) => {
      if (settled) return
      settled = true
      URL.revokeObjectURL(url)
      el.removeAttribute('src')
      resolve(value)
    }
    el.preload = 'metadata'
    el.muted = true
    el.onloadedmetadata = () => done(Number.isFinite(el.duration) && el.duration > 0 ? el.duration : null)
    el.onerror = () => done(null)
    window.setTimeout(() => done(null), timeoutMs)
    el.src = url
  })
}

function formatMinutes(seconds: number) {
  const m = seconds / 60
  return Number.isInteger(m) ? `${m} min` : `${m.toFixed(1)} min`
}

/**
 * Contrôles AVANT l'envoi: quota mensuel et durée max du plan. Évite
 * d'envoyer des centaines de Mo (souvent en 4G) pour un refus à l'arrivée.
 * Les erreurs réseau du préflight ne bloquent pas: le serveur revérifie tout.
 */
export async function preflightUpload(file: File, purpose: UploadPurpose = 'edit') {
  let check: UploadCheck | null = null
  try {
    check = await getUploadCheck(purpose)
  } catch {
    return
  }
  if (!check.can_upload) {
    throw new Error(check.reason || 'Quota mensuel atteint. Passe Pro pour continuer.')
  }
  if (file.size > check.max_upload_mb * 1024 * 1024) {
    throw new Error(`Fichier trop lourd. Maximum : ${check.max_upload_mb} Mo.`)
  }
  if (check.max_duration_s) {
    const duration = await probeLocalDuration(file)
    if (duration && duration > check.max_duration_s + 1) {
      throw new Error(
        `Cette vidéo dure ${formatMinutes(Math.round(duration))} : ton plan accepte ${formatMinutes(check.max_duration_s)} maximum. ` +
          'Coupe-la ou passe à un plan supérieur.',
      )
    }
  }
}

export async function uploadVideo(
  file: File,
  onProgress?: (percent: number) => void,
  purpose: UploadPurpose = 'edit',
) {
  validateVideoFile(file)

  await warmAuthSession()
  await preflightUpload(file, purpose)

  const formData = new FormData()
  formData.append('file', file)

  const uploadConfig = {
    headers: { 'Content-Type': 'multipart/form-data' },
    // Ne jamais couper côté navigateur: sur mobile, une vidéo de 3 minutes peut
    // dépasser 10 minutes selon la 4G/Wi-Fi. Le serveur/proxy garde ses propres
    // limites de sécurité; ici on attend la vraie réponse au lieu d'afficher
    // "timeout of 600000ms exceeded".
    timeout: 0,
    // Ne jamais réessayer automatiquement ce POST: si le serveur refuse après
    // réception du gros body, refaire la même requête redémarre l'upload à 0%.
    _skipAuthRetry: true,
    onUploadProgress: (e: ProgressEvent) => {
      if (e.total && onProgress) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  } as any

  const res = await client.post(`/videos/upload?purpose=${purpose}`, formData, uploadConfig)
  return res.data
}

export async function listVideos(skip = 0, limit = 20) {
  const res = await client.get(`/videos?skip=${skip}&limit=${limit}`)
  return res.data
}

export async function getVideo(id: string) {
  const res = await client.get(`/videos/${id}`)
  return res.data
}

export async function deleteVideo(id: string) {
  await client.delete(`/videos/${id}`)
}

function withAccessToken(url: string) {
  const token = localStorage.getItem('access_token')
  if (!token) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}access_token=${encodeURIComponent(token)}`
}

export function getStreamUrl(id: string) {
  // The HTML <video> element cannot send Authorization headers. Put the current
  // access token in the URL so the browser can stream metadata/ranges directly
  // instead of downloading the whole file with fetch() first.
  const base = import.meta.env.VITE_API_URL || '/api'
  return withAccessToken(`${base}/v1/videos/${id}/stream`)
}
