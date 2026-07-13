import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Link2, Scissors, Loader2, Download, Play, Flame, ArrowLeft, Clock,
} from 'lucide-react'
import JobProgress from '../components/video/JobProgress'
import { listModesFull, type ModeDescriptor } from '../api/jobs'
import {
  createClipsJob,
  downloadClip,
  getClipDownloadUrl,
  type ClipResult,
} from '../api/clips'
import { toast } from '../components/ui/Toast'

/** Styles proposés pour les clips (sous-ensemble des modes de montage v2). */
const CLIP_STYLE_IDS = [
  'pill_editorial', 'neon_hype', 'handwritten_note',
  'credit_saver_creator_edit', 'tiktok_viral',
]

function formatDuration(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function Clips() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [maxClips, setMaxClips] = useState(5)
  const [styles, setStyles] = useState<ModeDescriptor[]>([])
  const [selectedStyle, setSelectedStyle] = useState('pill_editorial')
  const [jobId, setJobId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [clips, setClips] = useState<ClipResult[] | null>(null)
  const [previewIndex, setPreviewIndex] = useState<number | null>(null)

  useEffect(() => {
    listModesFull()
      .then(({ modes }) => {
        const list = modes.filter((m) => CLIP_STYLE_IDS.includes(m.id))
        if (list.length > 0) {
          setStyles(list)
          if (!list.some((m) => m.id === selectedStyle)) setSelectedStyle(list[0].id)
        }
      })
      .catch(() => { /* la liste statique d'ids suffit */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = useCallback(async () => {
    const trimmed = url.trim()
    if (!trimmed) {
      toast('error', "Colle d'abord l'URL d'une vidéo (YouTube, TikTok…)")
      return
    }
    if (!/^https?:\/\//i.test(trimmed)) {
      toast('error', "L'URL doit commencer par http(s)://")
      return
    }
    setSubmitting(true)
    setClips(null)
    setPreviewIndex(null)
    try {
      const job = await createClipsJob({
        source_url: trimmed,
        mode: selectedStyle,
        options: { max_clips: maxClips },
      })
      setJobId(job.id)
      toast('info', 'Analyse de la vidéo lancée — détection des moments viraux…')
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast('error', detail || 'Impossible de lancer le traitement.')
    } finally {
      setSubmitting(false)
    }
  }, [url, selectedStyle, maxClips])

  const handleComplete = useCallback((result: Record<string, unknown>) => {
    const list = (result?.clips as ClipResult[] | undefined) ?? []
    setClips(list)
    const ok = list.filter((c) => c.output_path).length
    if (ok > 0) {
      setPreviewIndex(list.find((c) => c.output_path)?.index ?? null)
    }
  }, [])

  const okClips = (clips ?? []).filter((c) => c.output_path)
  const previewClip = okClips.find((c) => c.index === previewIndex) ?? null

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-dark-400 hover:text-white transition-colors"
          aria-label="Retour au dashboard"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Scissors className="w-6 h-6 text-primary-400" />
            Vidéo longue → Clips viraux
          </h1>
          <p className="text-dark-400 text-sm">
            Colle l'URL d'une vidéo (YouTube, TikTok…). L'IA détecte les meilleurs
            moments, les monte avec sous-titres et effets, et tu choisis les clips
            à télécharger.
          </p>
        </div>
      </div>

      {/* ---- Formulaire ---- */}
      <div className="card mb-6">
        <label className="block text-sm font-medium text-dark-300 mb-2">
          URL de la vidéo source
        </label>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Link2 className="w-4 h-4 text-dark-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=…"
              className="input-field pl-9"
              disabled={submitting || (!!jobId && clips === null)}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={submitting || (!!jobId && clips === null)}
            className="btn-primary flex items-center justify-center gap-2 whitespace-nowrap"
          >
            {submitting
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Scissors className="w-4 h-4" />}
            Créer les clips
          </button>
        </div>

        <div className="grid sm:grid-cols-2 gap-4 mt-5">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Style de montage des clips
            </label>
            <div className="space-y-2">
              {(styles.length > 0
                ? styles
                : CLIP_STYLE_IDS.map((id) => ({
                    id, name: id, icon: '🎬', description: '', pipeline: 'v2' as const, defaults: {},
                  }))
              ).map((m) => (
                <button
                  key={m.id}
                  onClick={() => setSelectedStyle(m.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg border text-sm flex items-center gap-2 transition-colors ${
                    selectedStyle === m.id
                      ? 'border-primary-500 bg-primary-500/10 text-white'
                      : 'border-dark-700 bg-dark-800/60 text-dark-300 hover:border-dark-500'
                  }`}
                >
                  <span>{m.icon}</span>
                  <span className="truncate">{m.name}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Nombre de clips maximum : <span className="text-white">{maxClips}</span>
            </label>
            <input
              type="range"
              min={1}
              max={10}
              value={maxClips}
              onChange={(e) => setMaxClips(Number(e.target.value))}
              className="w-full accent-primary-500"
            />
            <p className="text-xs text-dark-500 mt-2">
              L'IA garde uniquement les extraits vraiment « clippables » — tu peux
              recevoir moins de clips que le maximum demandé.
            </p>
          </div>
        </div>
      </div>

      {/* ---- Progression ---- */}
      {jobId && clips === null && (
        <div className="card mb-6">
          <JobProgress jobId={jobId} onComplete={handleComplete} />
        </div>
      )}

      {/* ---- Résultats ---- */}
      {clips !== null && (
        <div className="space-y-6">
          {previewClip && (
            <div className="card">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <Play className="w-4 h-4 text-primary-400" />
                Aperçu : {previewClip.title}
              </h2>
              <video
                key={previewClip.index}
                src={getClipDownloadUrl(jobId as string, previewClip.index)}
                controls
                playsInline
                className="w-full max-h-[70vh] rounded-lg bg-black mx-auto aspect-[9/16] sm:max-w-sm"
              />
            </div>
          )}

          <div>
            <h2 className="font-semibold mb-3">
              {okClips.length > 0
                ? `${okClips.length} clip(s) prêts — choisis ceux à télécharger`
                : 'Aucun clip n\'a pu être monté pour cette vidéo.'}
            </h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {(clips ?? []).map((clip) => (
                <div
                  key={clip.index}
                  className={`card !p-4 ${clip.output_path ? '' : 'opacity-60'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-semibold truncate">{clip.title}</p>
                      {clip.hook && (
                        <p className="text-xs text-dark-400 mt-1 line-clamp-2">
                          « {clip.hook} »
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-accent-500/15 text-accent-300 border border-accent-500/30">
                      <Flame className="w-3 h-3" /> {clip.score}
                    </span>
                  </div>
                  <p className="text-xs text-dark-500 mt-2 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDuration(clip.duration_s)}
                    {' · '}
                    source {formatDuration(clip.source_start)} → {formatDuration(clip.source_end)}
                  </p>
                  {clip.error && (
                    <p className="text-xs text-red-400 mt-2">
                      Échec du montage de ce clip. Les autres restent disponibles.
                    </p>
                  )}
                  {clip.output_path && (
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => setPreviewIndex(clip.index)}
                        className="btn-secondary !py-1.5 !px-3 text-sm flex items-center gap-1.5"
                      >
                        <Play className="w-3.5 h-3.5" /> Aperçu
                      </button>
                      <button
                        onClick={() => downloadClip(jobId as string, clip.index)}
                        className="btn-primary !py-1.5 !px-3 text-sm flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" /> Télécharger
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => { setJobId(null); setClips(null); setUrl(''); setPreviewIndex(null) }}
            className="btn-secondary"
          >
            Transformer une autre vidéo
          </button>
        </div>
      )}
    </div>
  )
}
