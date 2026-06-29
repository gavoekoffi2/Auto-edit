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

export async function uploadVideo(file: File, onProgress?: (percent: number) => void) {
  validateVideoFile(file)

  await warmAuthSession()

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

  const res = await client.post('/videos/upload', formData, uploadConfig)
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
