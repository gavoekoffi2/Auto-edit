import client from './client'

const MAX_FILE_SIZE_MB = 500

export async function uploadVideo(file: File, onProgress?: (percent: number) => void) {
  // Client-side file size validation
  const maxBytes = MAX_FILE_SIZE_MB * 1024 * 1024
  if (file.size > maxBytes) {
    throw new Error(`File too large. Maximum size: ${MAX_FILE_SIZE_MB}MB`)
  }

  // Validate file type
  const allowed = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska', 'video/webm']
  if (!allowed.includes(file.type) && !file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i)) {
    throw new Error('Invalid file type. Supported: MP4, MOV, AVI, MKV, WebM')
  }

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
