import client, { downloadWithAuth } from './client'

export type PipelineVersion = 'v1' | 'v2'

/** Stratégie visuelle d'un rendu. */
export type VisualMode = 'ai_broll' | 'credit_saver' | 'auto_fallback'
/** Familles de motion design (look varié d'une vidéo à l'autre). */
export type MotionPreset =
  | 'clean_fintech' | 'neon_social' | 'african_premium'
  | 'minimal_creator' | 'kinetic_education'
  | 'editorial_paper' | 'sketch_notes'
/** Templates de sous-titres animés du moteur. */
export type SubtitleTemplate =
  | 'tiktok_yellow' | 'neon_pop' | 'bold_box' | 'gold_lux' | 'bangers_fun'
  | 'pill_editorial' | 'neon_hype' | 'handwritten_note'

export interface JobOptions {
  remove_silence?: boolean
  dynamic_captions?: boolean
  ai_broll?: boolean
  /** Scènes motion design illustrées (dessins animés qui illustrent le discours) */
  motion_design?: boolean
  music?: boolean
  sfx?: boolean
  vertical_9_16?: boolean
  final_cta?: boolean
  broll_style?: string
  broll_demographic?: 'african' | 'caucasian' | 'global'
  /** ai_broll | credit_saver | auto_fallback — par défaut le preset du mode. */
  visual_mode?: VisualMode
  /** Force une famille motion design (sinon seed stable de la vidéo). */
  motion_preset?: MotionPreset
  /** Template de sous-titres animés (sinon déduit du mode/style choisi). */
  subtitle_template?: SubtitleTemplate
  /** Fonctionnalité Clips: nombre max de shorts extraits d'une vidéo longue (1-10). */
  max_clips?: number
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

export interface ModeDescriptor {
  id: string
  name: string
  icon: string
  description: string
  pipeline: PipelineVersion
  /** true pour le mode sélectionné par défaut (montage créateur économique). */
  default?: boolean
  defaults: JobOptions
}

export interface ModesResponse {
  modes: ModeDescriptor[]
  default_mode: string
}

export async function listModesFull(): Promise<ModesResponse> {
  const res = await client.get('/jobs/modes')
  return {
    modes: (res.data?.modes ?? []) as ModeDescriptor[],
    default_mode: (res.data?.default_mode ?? '') as string,
  }
}

export async function listModes(): Promise<ModeDescriptor[]> {
  const { modes } = await listModesFull()
  return modes
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

function withAccessToken(url: string) {
  const token = localStorage.getItem('access_token')
  if (!token) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}access_token=${encodeURIComponent(token)}`
}

export function getJobDownloadUrl(jobId: string) {
  const base = import.meta.env.VITE_API_URL || '/api'
  return withAccessToken(`${base}/v1/jobs/${jobId}/download`)
}

/**
 * Download the rendered montage.
 *
 * Strategy: refresh the session first (a 15-min access token can expire during
 * a long render — the old code then hit a silent 401 and "le téléchargement ne
 * fonctionnait pas"), then trigger a NATIVE browser download via a direct
 * link. Native downloads stream straight to disk (no blob in RAM — large
 * videos crashed mobile tabs) and support resume thanks to the range-aware
 * backend. The blob fetch stays as a last-resort fallback.
 */
export async function downloadJobResult(jobId: string) {
  try {
    // Any authenticated call refreshes an expired token via the interceptor.
    await client.get('/auth/me', { timeout: 15000 })
  } catch {
    /* if this fails the interceptor already redirected to /login */
  }

  const url = getJobDownloadUrl(jobId)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = `cutforge_${jobId}.mp4`
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch {
    await downloadWithAuth(`/jobs/${jobId}/download`, `cutforge_${jobId}.mp4`)
  }
}

export async function cancelJob(jobId: string) {
  const res = await client.post(`/jobs/${jobId}/cancel`)
  return res.data
}
