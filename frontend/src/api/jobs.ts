import client from './client'

export interface JobCreateData {
  video_id: string
  job_type?: string
  mode?: string
  params?: Record<string, unknown>
}

export async function createJob(data: JobCreateData) {
  const res = await client.post('/jobs', data)
  return res.data
}

export async function getJob(id: string) {
  const res = await client.get(`/jobs/${id}`)
  return res.data
}

export async function listJobs(videoId?: string) {
  const url = videoId ? `/jobs?video_id=${videoId}` : '/jobs'
  const res = await client.get(url)
  return res.data
}

export function getDownloadUrl(jobId: string) {
  const token = localStorage.getItem('access_token')
  const base = import.meta.env.VITE_API_URL || '/api'
  return `${base}/v1/jobs/${jobId}/download?token=${token}`
}
