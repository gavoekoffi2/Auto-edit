import { useState } from 'react'
import { Check, Copy, Scissors, ListOrdered, ShieldCheck } from 'lucide-react'

interface Chapter { start: number; title: string }

interface LongformResult {
  chapters?: Chapter[]
  chapters_text?: string
  chapters_youtube_valid?: boolean
  cut?: {
    source_duration?: number
    kept_duration?: number
    removed_duration?: number
    ranges?: number
    removed_counts?: Record<string, number>
  }
  graphics?: { keyword_popups?: number; chapter_cards?: number }
  audio?: { final_lufs?: number | null; music?: string | null }
  checks?: { sync_ok?: boolean; av_diff_ms?: number; loudness_ok?: boolean }
}

const REASONS: Record<string, string> = {
  faux_depart: 'faux départs',
  phrase_abandonnee: 'phrases abandonnées',
  phrase_repetee: 'phrases redites',
  begaiement: 'bégaiements',
  tic_de_langage: 'tics de langage',
  marqueur_reprise: '« je reprends »',
}

function fmt(t = 0): string {
  const s = Math.max(0, Math.round(t))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(2, '0')
  return h ? `${h}:${mm}:${String(sec).padStart(2, '0')}` : `${mm}:${String(sec).padStart(2, '0')}`
}

export default function LongformRecap({ data: raw, style }: { data: Record<string, unknown>; style?: string }) {
  const data = raw as LongformResult
  const [copied, setCopied] = useState(false)
  const cut = data.cut ?? {}
  const counts = cut.removed_counts ?? {}
  const saved = (cut.source_duration ?? 0) - (cut.kept_duration ?? 0)

  const copy = async () => {
    if (!data.chapters_text) return
    try {
      await navigator.clipboard.writeText(data.chapters_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      /* presse-papiers indisponible : le texte reste sélectionnable */
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold">Montage YouTube long</h3>
        {style && <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-dark-200">Style : {style}</span>}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-black/30 p-3">
          <p className="text-xs text-dark-400">Durée</p>
          <p className="mt-1 text-lg font-semibold">{fmt(cut.source_duration)} → {fmt(cut.kept_duration)}</p>
          <p className="text-xs text-dark-400">{fmt(saved)} de temps mort retiré</p>
        </div>
        <div className="rounded-xl bg-black/30 p-3">
          <p className="flex items-center gap-1 text-xs text-dark-400"><Scissors className="h-3 w-3" /> Coupes</p>
          <p className="mt-1 text-lg font-semibold">{cut.ranges ?? 0} plans</p>
          <p className="text-xs text-dark-400">
            {Object.entries(counts).map(([k, v]) => `${v} ${REASONS[k] ?? k}`).join(' · ') || 'aucune reprise détectée'}
          </p>
        </div>
        <div className="rounded-xl bg-black/30 p-3">
          <p className="flex items-center gap-1 text-xs text-dark-400"><ShieldCheck className="h-3 w-3" /> Vérifications</p>
          <p className="mt-1 text-sm">
            {data.checks?.sync_ok ? '✅' : '⚠️'} Synchro image/son ({data.checks?.av_diff_ms ?? '?'} ms)
          </p>
          <p className="text-sm">
            {data.checks?.loudness_ok ? '✅' : '⚠️'} Son {data.audio?.final_lufs ?? '?'} LUFS
          </p>
        </div>
      </div>

      {!!data.chapters?.length && (
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-medium">
              <ListOrdered className="h-4 w-4" /> Chapitres à coller dans la description YouTube
            </p>
            <button onClick={copy} className="flex items-center gap-1 rounded-lg border border-white/15 px-3 py-1.5 text-xs hover:border-white/30">
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copié' : 'Copier'}
            </button>
          </div>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-black/40 p-3 text-sm text-dark-100">
            {data.chapters_text}
          </pre>
          {data.chapters_youtube_valid === false && (
            <p className="mt-1 text-xs text-amber-300">
              Vidéo trop courte pour des chapitres YouTube valides (3 chapitres de 10 s minimum).
            </p>
          )}
        </div>
      )}
    </div>
  )
}
