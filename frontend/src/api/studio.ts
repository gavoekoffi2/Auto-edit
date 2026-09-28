import client from './client'

/** Les 16 grammaires de montage du Studio face caméra. */
export type MontageId =
  | 'plein_cadre' | 'presentateur' | 'fenetre' | 'telephone' | 'kinetique'
  | 'ecran_scinde' | 'zoom_rythme' | 'mur_polaroid' | 'journal_tv' | 'magazine'
  | 'stories' | 'jeu_video' | 'podcast' | 'documentaire' | 'bento' | 'voyage'

export interface StylePalette {
  dark: string
  dark2: string
  light: string
  light2: string
  ink: string
  accent: string
  accent2: string
  bad: string
  good: string
}

export interface StudioStyle {
  id: string
  name: string
  description: string
  validated: boolean
  montage: MontageId
  montage_name: string
  montage_desc: string
  palette: StylePalette
  head_font: 'Anton' | 'Bebas' | 'DMSerif'
  chrome: string
  panel: string
  transition: string
  captions: string
  tone: 'dark' | 'light'
  mood: string
}

export interface RecentStyle {
  id: string
  name?: string
  montage?: MontageId
}

export interface StylesResponse {
  styles: StudioStyle[]
  recent: RecentStyle[]
  logo_asset: string | null
}

export async function listStudioStyles(): Promise<StylesResponse> {
  const res = await client.get('/jobs/styles')
  return {
    styles: (res.data?.styles ?? []) as StudioStyle[],
    recent: (res.data?.recent ?? []) as RecentStyle[],
    logo_asset: (res.data?.logo_asset ?? null) as string | null,
  }
}

export async function uploadLogo(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post('/jobs/assets/logo', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  return res.data.asset_id as string
}

export function logoUrl(assetId: string) {
  const base = import.meta.env.VITE_API_URL || '/api'
  const token = localStorage.getItem('access_token')
  return `${base}/v1/jobs/assets/logo/${assetId}${token ? `?access_token=${encodeURIComponent(token)}` : ''}`
}

export const MONTAGE_LABELS: Record<MontageId, string> = {
  plein_cadre: 'Plein cadre',
  presentateur: 'Présentateur',
  fenetre: 'Fenêtre',
  telephone: 'Téléphone',
  kinetique: 'Typo cinétique',
  ecran_scinde: 'Écran scindé',
  zoom_rythme: 'Zoom rythmé',
  mur_polaroid: 'Mur de polaroids',
  journal_tv: 'Journal TV',
  magazine: 'Magazine',
  stories: 'Story Instagram',
  jeu_video: 'Jeu vidéo',
  podcast: 'Podcast',
  documentaire: 'Documentaire',
  bento: 'Bento',
  voyage: 'Voyage plan-séquence',
}

/** Étapes du moteur, alignées sur les pourcentages envoyés par le backend. */
export const STUDIO_STEPS: { at: number; label: string; hint: string }[] = [
  { at: 0, label: 'Transcription', hint: 'Chaque mot est minuté' },
  { at: 12, label: 'Coupes précises', hint: 'Hésitations, répétitions, silences' },
  { at: 18, label: 'Assemblage 9:16', hint: 'Zooms alternés qui masquent les coupes' },
  { at: 26, label: 'Style unique', hint: 'Choisi selon le sujet et tes derniers montages' },
  { at: 30, label: 'Plan du motion design', hint: 'Accroche, cartes, démonstrations, fin' },
  { at: 34, label: 'Montage animé', hint: 'Rendu image par image' },
  { at: 84, label: 'Son', hint: 'Voix nettoyée, effets sonores, musique' },
  { at: 92, label: 'Export', hint: 'MP4 prêt pour TikTok et Facebook' },
]
