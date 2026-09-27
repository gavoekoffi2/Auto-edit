import client from './client'

export interface AdTemplate { id: string; name: string; description: string; accent: string; dark: string }
export interface AdAngle { id: string; name: string; structure: string }

export interface InterviewTurn {
  reply: string
  brief: Record<string, unknown>
  done: boolean
  suggestions: string[]
  field: string | null
}

export interface StoryBeat { text: string; scene: { type: string; [k: string]: unknown }; pause_after?: number }
export interface Storyboard { angle: string; template: string; title?: string; notes?: string[]; beats: StoryBeat[] }

export interface AdProject {
  id: string
  title: string
  template: string
  angle: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  stage?: string | null
  error_message?: string | null
  brief: Record<string, unknown>
  result?: { duration?: number; script?: string[]; voice_provider?: string; notes?: string[] } | null
  created_at: string
  completed_at?: string | null
}

export async function getAdCatalog(): Promise<{ templates: AdTemplate[]; angles: AdAngle[] }> {
  return (await client.get('/ads/catalog')).data
}

export async function interviewTurn(brief: Record<string, unknown>, answer?: string, history: { role: string; content: string }[] = []): Promise<InterviewTurn> {
  return (await client.post('/ads/interview', { brief, answer, history }, { timeout: 60000 })).data
}

export async function previewScript(brief: Record<string, unknown>): Promise<{ brief: Record<string, unknown>; storyboard: Storyboard }> {
  return (await client.post('/ads/script', { brief }, { timeout: 120000 })).data
}

export async function createAd(brief: Record<string, unknown>, storyboard?: Storyboard): Promise<AdProject> {
  return (await client.post('/ads', { brief, storyboard })).data
}

export async function listAds(): Promise<AdProject[]> {
  return (await client.get('/ads')).data
}

export async function getAd(id: string): Promise<AdProject> {
  return (await client.get(`/ads/${id}`)).data
}

export async function cancelAd(id: string): Promise<AdProject> {
  return (await client.post(`/ads/${id}/cancel`)).data
}

export async function deleteAd(id: string): Promise<void> {
  await client.delete(`/ads/${id}`)
}

function withToken(url: string) {
  const token = localStorage.getItem('access_token')
  if (!token) return url
  return `${url}${url.includes('?') ? '&' : '?'}access_token=${encodeURIComponent(token)}`
}

const API_URL = import.meta.env.VITE_API_URL || '/api'
export const adVideoUrl = (id: string) => withToken(`${API_URL}/v1/ads/${id}/video`)
export const adThumbUrl = (id: string) => withToken(`${API_URL}/v1/ads/${id}/thumbnail`)
