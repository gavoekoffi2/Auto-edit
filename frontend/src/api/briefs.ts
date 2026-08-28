import client from './client'

export type AdTemplateId =
  | 'direct_response'
  | 'urgency_proof'
  | 'saas_explainer'
  | 'facecam_editorial'
  | 'facecam_neon'
  | 'facecam_notes'

export type BriefInput = {
  description: string
  template_id: AdTemplateId
  brand_name: string
  audience: string
  offer: string
  proof: string
  cta: string
  tone: 'expert' | 'direct' | 'premium' | 'chaleureux'
  format: '9:16' | '1:1' | '16:9'
  duration_s: number
}

export type StoryScene = {
  order: number
  role: string
  start_s: number
  end_s: number
  narration: string
  visual_direction: string
  motion: string
  audio: string
  text_overlay: string
}

export type BriefPreview = {
  template_id: AdTemplateId
  format: string
  duration_s: number
  title: string
  summary: string
  scenes: StoryScene[]
  render_plan: Record<string, unknown>
  warnings: string[]
}

export async function previewBrief(input: BriefInput): Promise<BriefPreview> {
  const response = await client.post<BriefPreview>('/briefs/preview', input)
  return response.data
}
