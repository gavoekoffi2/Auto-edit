import client from './client'

export const MAX_FILE_SIZE_MB = 2048
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

export async function uploadVideo(file: File, onProgress?: (percent: number) => void) {
  validateVideoFile(file)

  const formData = new FormData()
  formData.append('file', file)

  const res = await client.post('/videos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000, // 10min timeout for large uploads
    onUploadProgress: (e) => {
      if (e.total && onProgress) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  })
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

export function getStreamUrl(id: string) {
  // Stream endpoint is protected by auth header via client interceptor.
  // We return just the path - VideoPlayer will need to use fetch with auth.
  const base = import.meta.env.VITE_API_URL || '/api'
  return `${base}/v1/videos/${id}/stream`
}
