import client from './client'
import type { JobOptions } from './jobs'

/** Un clip extrait d'une vidéo longue par la fonctionnalité Clips. */
export interface ClipResult {
  index: number
  title: string
  hook?: string
  reason?: string
  score: number
  source_start: number
  source_end: number
  duration_s: number
  /** Présent quand le montage du clip a réussi. */
  output_path?: string
  size_bytes?: number
  error?: string
}

/** Un moment proposé par l'analyse (étape 1), avant sélection. */
export interface MomentSuggestion {
  start: number
  end: number
  title: string
  hook?: string
  reason?: string
  score: number
  excerpt?: string
}

export interface ClipsCreateData {
  source_url?: string
  video_id?: string
  mode?: string
  options?: JobOptions
}

export async function createClipsJob(data: ClipsCreateData) {
  const res = await client.post('/clips', data)
  return res.data
}

/** Étape 2 : rendre uniquement les extraits sélectionnés/ajustés. */
export interface ClipsRenderData {
  clips: Array<{
    start: number
    end: number
    title?: string
    hook?: string
    reason?: string
    score?: number
  }>
  mode?: string
  options?: JobOptions
}

export async function renderSelectedClips(analyzeJobId: string, data: ClipsRenderData) {
  const res = await client.post(`/clips/${analyzeJobId}/render`, data)
  return res.data
}

function withAccessToken(url: string) {
  const token = localStorage.getItem('access_token')
  if (!token) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}access_token=${encodeURIComponent(token)}`
}

/** URL (authentifiée) de téléchargement/streaming d'UN clip du job. */
export function getClipDownloadUrl(jobId: string, clipIndex: number) {
  const base = import.meta.env.VITE_API_URL || '/api'
  return withAccessToken(`${base}/v1/jobs/${jobId}/clips/${clipIndex}/download`)
}

/** Déclenche un téléchargement navigateur natif du clip (streaming disque). */
export async function downloadClip(jobId: string, clipIndex: number) {
  try {
    // Rafraîchit la session si le token a expiré pendant le rendu.
    await client.get('/auth/me', { timeout: 15000 })
  } catch {
    /* l'intercepteur a déjà redirigé vers /login si besoin */
  }
  const a = document.createElement('a')
  a.href = getClipDownloadUrl(jobId, clipIndex)
  a.download = `cutforge_clip_${clipIndex + 1}.mp4`
  document.body.appendChild(a)
  a.click()
  a.remove()
}
