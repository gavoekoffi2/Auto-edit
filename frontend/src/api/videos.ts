import client from './client'

export async function uploadVideo(file: File, onProgress?: (percent: number) => void) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await client.post('/videos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
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
  const token = localStorage.getItem('access_token')
  const base = import.meta.env.VITE_API_URL || '/api'
  return `${base}/v1/videos/${id}/stream?token=${token}`
}
