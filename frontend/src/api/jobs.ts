import client, { downloadWithAuth } from './client'

export type PipelineVersion = 'v1' | 'v2'

export interface JobOptions {
  remove_silence?: boolean
  dynamic_captions?: boolean
  ai_broll?: boolean
  music?: boolean
  sfx?: boolean
  vertical_9_16?: boolean
  final_cta?: boolean
  broll_style?: string
  cta_text?: string
  logo_text?: string
}

export interface JobCreateData {
  video_id: string
  job_type?: string
  mode?: string
  params?: Record<string, unknown>
  pipeline_version?: PipelineVersion
  options?: JobOptions
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

export async function downloadJobResult(jobId: string) {
  await downloadWithAuth(`/jobs/${jobId}/download`, `autoedit_${jobId}.mp4`)
}
