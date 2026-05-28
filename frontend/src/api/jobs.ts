import client, { downloadWithAuth } from './client'

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

export async function cancelJob(id: string) {
  const res = await client.post(`/jobs/${id}/cancel`)
  return res.data
}

export async function downloadJobResult(jobId: string) {
  await downloadWithAuth(`/jobs/${jobId}/download`, `autoedit_${jobId}.mp4`)
}
