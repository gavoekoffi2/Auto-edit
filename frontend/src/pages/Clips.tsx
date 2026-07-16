import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Link2, Scissors, Loader2, Download, Play, Sparkles, ArrowLeft, Clock,
  Upload, CheckSquare, Square, Trash2, Pencil,
} from 'lucide-react'
import JobProgress from '../components/video/JobProgress'
import { listModesFull, type ModeDescriptor } from '../api/jobs'
import {
  createClipsJob,
  renderSelectedClips,
  downloadClip,
  getClipDownloadUrl,
  type ClipResult,
  type MomentSuggestion,
} from '../api/clips'
import { uploadVideo, validateVideoFile, getStreamUrl } from '../api/videos'
import { toast } from '../components/ui/Toast'

/** Styles proposés pour les clips (sous-ensemble des modes de montage v2). */
const CLIP_STYLE_IDS = [
  'pill_editorial', 'neon_hype', 'handwritten_note',
  'credit_saver_creator_edit', 'tiktok_viral',
]

type Phase = 'input' | 'analyzing' | 'selecting' | 'rendering' | 'done'

interface EditableMoment extends MomentSuggestion {
  selected: boolean
}

function formatDuration(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function extractApiError(e: unknown): string | null {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in (detail as object)) {
    return String((detail as { message?: string }).message)
  }
  return null
}

export default function Clips() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('input')
  const [url, setUrl] = useState('')
  const [rightsConfirmed, setRightsConfirmed] = useState(false)
  const [uploadPct, setUploadPct] = useState<number | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const [maxClips, setMaxClips] = useState(5)
  const [styles, setStyles] = useState<ModeDescriptor[]>([])
  const [selectedStyle, setSelectedStyle] = useState('pill_editorial')

  const [analyzeJobId, setAnalyzeJobId] = useState<string | null>(null)
  const [sourceVideoId, setSourceVideoId] = useState<string | null>(null)
  const [moments, setMoments] = useState<EditableMoment[]>([])
  const [previewMoment, setPreviewMoment] = useState<number | null>(null)

  const [renderJobId, setRenderJobId] = useState<string | null>(null)
  const [clips, setClips] = useState<ClipResult[] | null>(null)
  const [previewClip, setPreviewClip] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

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

  // ---- Étape 1 : lancer l'analyse (URL ou vidéo uploadée) -----------------
  const startAnalyze = useCallback(async (data: { source_url?: string; video_id?: string }) => {
    setSubmitting(true)
    try {
      const job = await createClipsJob({
        ...data,
        mode: selectedStyle,
        options: { max_clips: maxClips },
      })
      setAnalyzeJobId(job.id)
      setSourceVideoId(job.video_id)
      setPhase('analyzing')
      toast('info', 'Analyse lancée : transcription puis détection des moments forts…')
    } catch (e) {
      toast('error', extractApiError(e) || "Impossible de lancer l'analyse.")
    } finally {
      setSubmitting(false)
    }
  }, [selectedStyle, maxClips])

  const handleSubmitUrl = useCallback(async () => {
    const trimmed = url.trim()
    if (!trimmed) { toast('error', "Colle d'abord l'URL d'une vidéo publique"); return }
    if (!/^https?:\/\//i.test(trimmed)) { toast('error', "L'URL doit commencer par http(s)://"); return }
    if (!rightsConfirmed) { toast('error', 'Confirme que tu as les droits sur cette vidéo.'); return }
    await startAnalyze({ source_url: trimmed })
  }, [url, rightsConfirmed, startAnalyze])

  const handleFilePicked = useCallback(async (file: File) => {
    if (!rightsConfirmed) { toast('error', 'Confirme que tu as les droits sur cette vidéo.'); return }
    try {
      validateVideoFile(file)   // lève une erreur descriptive si invalide
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Fichier invalide.')
      return
    }
    setUploadPct(0)
    try {
      const video = await uploadVideo(file, (pct) => setUploadPct(pct))
      setUploadPct(null)
      await startAnalyze({ video_id: video.id })
    } catch (e) {
      setUploadPct(null)
      toast('error', extractApiError(e) || "L'envoi du fichier a échoué.")
    }
  }, [rightsConfirmed, startAnalyze])

  // ---- Fin d'analyse : proposer la sélection ------------------------------
  const handleAnalyzeComplete = useCallback((result: Record<string, unknown>) => {
    const found = (result?.moments as MomentSuggestion[] | undefined) ?? []
    if (result?.stage === 'moments_ready' && found.length > 0) {
      setMoments(found.map((m) => ({ ...m, selected: true })))
      setPreviewMoment(0)
      setPhase('selecting')
    } else {
      // Ancien format (rendu direct) — on saute à la galerie.
      const list = (result?.clips as ClipResult[] | undefined) ?? []
      setClips(list)
      setPhase('done')
    }
  }, [])

  // ---- Étape 2 : rendre la sélection --------------------------------------
  const handleRender = useCallback(async () => {
    if (!analyzeJobId) return
    const selection = moments.filter((m) => m.selected)
    if (selection.length === 0) { toast('error', 'Sélectionne au moins un extrait.'); return }
    setSubmitting(true)
    try {
      const job = await renderSelectedClips(analyzeJobId, {
        clips: selection.map(({ start, end, title, hook, reason, score }) => ({
          start, end, title, hook, reason, score,
        })),
        mode: selectedStyle,
      })
      setRenderJobId(job.id)
      setPhase('rendering')
      toast('info', `Montage de ${selection.length} clip(s) lancé — style ${selectedStyle}`)
    } catch (e) {
      toast('error', extractApiError(e) || 'Impossible de lancer le rendu.')
    } finally {
      setSubmitting(false)
    }
  }, [analyzeJobId, moments, selectedStyle])

  const handleRenderComplete = useCallback((result: Record<string, unknown>) => {
    const list = (result?.clips as ClipResult[] | undefined) ?? []
    setClips(list)
    setPreviewClip(list.find((c) => c.output_path)?.index ?? null)
    setPhase('done')
  }, [])

  const updateMoment = (i: number, patch: Partial<EditableMoment>) => {
    setMoments((ms) => ms.map((m, j) => (j === i ? { ...m, ...patch } : m)))
  }

  const reset = () => {
    setPhase('input'); setUrl(''); setAnalyzeJobId(null); setRenderJobId(null)
    setMoments([]); setClips(null); setPreviewClip(null); setPreviewMoment(null)
    setSourceVideoId(null)
  }

  const okClips = (clips ?? []).filter((c) => c.output_path)
  const selectedCount = moments.filter((m) => m.selected).length
  const shownClip = okClips.find((c) => c.index === previewClip) ?? null

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center gap-4">
        <button onClick={() => navigate('/dashboard')}
          className="text-dark-400 hover:text-white transition-colors" aria-label="Retour au dashboard">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Scissors className="w-6 h-6 text-primary-400" />
            Vidéo longue → Clips
          </h1>
          <p className="text-dark-400 text-sm">
            Importe une vidéo (URL publique ou fichier). L'IA propose les meilleurs
            extraits, tu choisis ceux à monter, puis tu télécharges tes clips.
          </p>
        </div>
      </div>

      {/* ================= Étape 1 : import ================= */}
      {phase === 'input' && (
        <div className="card mb-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              URL de la vidéo source
            </label>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Link2 className="w-4 h-4 text-dark-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input type="url" value={url} onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=…"
                  className="input-field pl-9" disabled={submitting} />
              </div>
              <button onClick={handleSubmitUrl} disabled={submitting}
                className="btn-primary flex items-center justify-center gap-2 whitespace-nowrap">
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Analyser la vidéo
              </button>
            </div>
            <p className="text-xs text-dark-500 mt-2">
              Vidéos publiques YouTube, TikTok, Facebook, Vimeo et la plupart des
              plateformes publiques prises en charge par yt-dlp. Aucune intégration
              officielle avec ces marques.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="h-px bg-dark-700 flex-1" />
            <span className="text-xs text-dark-500">ou</span>
            <div className="h-px bg-dark-700 flex-1" />
          </div>

          <div>
            <input ref={fileInput} type="file" accept="video/*" className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) handleFilePicked(f)
                e.target.value = ''
              }} />
            <button onClick={() => fileInput.current?.click()}
              disabled={submitting || uploadPct !== null}
              className="btn-secondary w-full flex items-center justify-center gap-2">
              {uploadPct !== null
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Envoi… {uploadPct}%</>
                : <><Upload className="w-4 h-4" /> Importer un fichier depuis cet appareil</>}
            </button>
            {uploadPct !== null && (
              <div className="mt-2 h-1.5 bg-dark-800 rounded-full overflow-hidden">
                <div className="h-full bg-primary-500 transition-all" style={{ width: `${uploadPct}%` }} />
              </div>
            )}
            <p className="text-xs text-dark-500 mt-2">
              MP4, MOV, MKV, WEBM… — durée max selon ton plan (30 min en gratuit).
            </p>
          </div>

          <label className="flex items-start gap-2 text-sm text-dark-300 cursor-pointer">
            <input type="checkbox" checked={rightsConfirmed}
              onChange={(e) => setRightsConfirmed(e.target.checked)}
              className="mt-0.5 accent-primary-500" />
            <span>
              Je confirme avoir les droits nécessaires sur cette vidéo (c'est ma
              vidéo, ou j'ai l'autorisation de son auteur).
            </span>
          </label>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Style de montage des clips
              </label>
              <div className="space-y-2">
                {(styles.length > 0 ? styles
                  : CLIP_STYLE_IDS.map((id) => ({
                      id, name: id, icon: '🎬', description: '', pipeline: 'v2' as const, defaults: {},
                    }))
                ).map((m) => (
                  <button key={m.id} onClick={() => setSelectedStyle(m.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg border text-sm flex items-center gap-2 transition-colors ${
                      selectedStyle === m.id
                        ? 'border-primary-500 bg-primary-500/10 text-white'
                        : 'border-dark-700 bg-dark-800/60 text-dark-300 hover:border-dark-500'
                    }`}>
                    <span>{m.icon}</span>
                    <span className="truncate">{m.name}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Extraits proposés maximum : <span className="text-white">{maxClips}</span>
              </label>
              <input type="range" min={1} max={10} value={maxClips}
                onChange={(e) => setMaxClips(Number(e.target.value))}
                className="w-full accent-primary-500" />
              <p className="text-xs text-dark-500 mt-2">
                Tu choisiras ensuite lesquels monter — rien n'est rendu sans ta
                sélection, et le maximum réel dépend de ton plan.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ================= Analyse en cours ================= */}
      {phase === 'analyzing' && analyzeJobId && (
        <div className="card mb-6">
          <JobProgress jobId={analyzeJobId} onComplete={handleAnalyzeComplete} />
        </div>
      )}

      {/* ================= Étape 2 : sélection ================= */}
      {phase === 'selecting' && (
        <div className="space-y-6">
          {previewMoment !== null && moments[previewMoment] && sourceVideoId && (
            <div className="card">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <Play className="w-4 h-4 text-primary-400" />
                Aperçu de l'extrait : {moments[previewMoment].title}
              </h2>
              <video
                key={`${previewMoment}-${moments[previewMoment].start}`}
                src={`${getStreamUrl(sourceVideoId)}#t=${moments[previewMoment].start},${moments[previewMoment].end}`}
                controls playsInline preload="metadata"
                className="w-full max-h-[50vh] rounded-lg bg-black" />
              <p className="text-xs text-dark-500 mt-2">
                Aperçu de la vidéo source (avant montage). Le clip final sera
                vertical, sous-titré et monté avec le style choisi.
              </p>
            </div>
          )}

          <div>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h2 className="font-semibold">
                {moments.length} extraits proposés — sélectionne ceux à monter
              </h2>
              <div className="flex gap-2">
                <button className="btn-secondary !py-1.5 !px-3 text-sm"
                  onClick={() => setMoments((ms) => ms.map((m) => ({ ...m, selected: true })))}>
                  Tout sélectionner
                </button>
                <button onClick={handleRender} disabled={submitting || selectedCount === 0}
                  className="btn-primary !py-1.5 !px-4 text-sm flex items-center gap-2">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scissors className="w-4 h-4" />}
                  Monter la sélection ({selectedCount})
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {moments.map((m, i) => (
                <div key={i} className={`card !p-4 ${m.selected ? 'border-primary-500/40' : 'opacity-70'}`}>
                  <div className="flex items-start gap-3">
                    <button onClick={() => updateMoment(i, { selected: !m.selected })}
                      className="mt-1 text-primary-400" aria-label="Sélectionner cet extrait">
                      {m.selected ? <CheckSquare className="w-5 h-5" /> : <Square className="w-5 h-5" />}
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Pencil className="w-3.5 h-3.5 text-dark-500 shrink-0" />
                        <input value={m.title}
                          onChange={(e) => updateMoment(i, { title: e.target.value })}
                          className="bg-transparent border-b border-dark-700 focus:border-primary-500 outline-none font-semibold w-full text-sm py-0.5"
                          maxLength={120} />
                      </div>
                      {m.hook && (
                        <p className="text-xs text-dark-400 mt-1.5">« {m.hook} »</p>
                      )}
                      {m.reason && (
                        <p className="text-xs text-accent-300/90 mt-1">
                          Pourquoi cet extrait : {m.reason}
                        </p>
                      )}
                      {m.excerpt && (
                        <details className="mt-1.5">
                          <summary className="text-xs text-dark-500 cursor-pointer">Transcript de l'extrait</summary>
                          <p className="text-xs text-dark-400 mt-1">{m.excerpt}</p>
                        </details>
                      )}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2 text-xs text-dark-500">
                        <span className="inline-flex items-center gap-1">
                          <Sparkles className="w-3 h-3 text-accent-300" />
                          Potentiel estimé : {m.score}/100
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDuration(m.end - m.start)} ({formatDuration(m.start)} → {formatDuration(m.end)})
                        </span>
                        <label className="inline-flex items-center gap-1">
                          Début
                          <input type="number" step={1} min={0} value={Math.round(m.start)}
                            onChange={(e) => updateMoment(i, { start: Math.max(0, Number(e.target.value)) })}
                            className="w-16 bg-dark-800 border border-dark-700 rounded px-1.5 py-0.5 text-white" />
                        </label>
                        <label className="inline-flex items-center gap-1">
                          Fin
                          <input type="number" step={1} min={0} value={Math.round(m.end)}
                            onChange={(e) => updateMoment(i, { end: Math.max(0, Number(e.target.value)) })}
                            className="w-16 bg-dark-800 border border-dark-700 rounded px-1.5 py-0.5 text-white" />
                        </label>
                      </div>
                    </div>
                    <div className="flex flex-col gap-2 shrink-0">
                      <button onClick={() => setPreviewMoment(i)}
                        className="btn-secondary !py-1 !px-2.5 text-xs flex items-center gap-1">
                        <Play className="w-3 h-3" /> Aperçu
                      </button>
                      <button onClick={() => setMoments((ms) => ms.filter((_, j) => j !== i))}
                        className="text-dark-500 hover:text-red-400 text-xs flex items-center gap-1 justify-center">
                        <Trash2 className="w-3 h-3" /> Retirer
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-dark-500 mt-3">
              Le « potentiel estimé » est un score éditorial indicatif (force du
              hook, autonomie de l'idée, émotion, chiffres) — pas une garantie de
              viralité.
            </p>
          </div>
        </div>
      )}

      {/* ================= Rendu en cours ================= */}
      {phase === 'rendering' && renderJobId && (
        <div className="card mb-6">
          <JobProgress jobId={renderJobId} onComplete={handleRenderComplete} />
        </div>
      )}

      {/* ================= Galerie finale ================= */}
      {phase === 'done' && clips !== null && (
        <div className="space-y-6">
          {shownClip && renderJobId && (
            <div className="card">
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <Play className="w-4 h-4 text-primary-400" />
                Aperçu : {shownClip.title}
              </h2>
              <video key={shownClip.index}
                src={getClipDownloadUrl(renderJobId, shownClip.index)}
                controls playsInline preload="metadata"
                className="w-full max-h-[70vh] rounded-lg bg-black mx-auto aspect-[9/16] sm:max-w-sm" />
            </div>
          )}

          <div>
            <h2 className="font-semibold mb-3">
              {okClips.length > 0
                ? `${okClips.length} clip(s) prêts — télécharge ceux que tu veux`
                : "Aucun clip n'a pu être monté pour cette vidéo."}
            </h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {(clips ?? []).map((clip) => (
                <div key={clip.index} className={`card !p-4 ${clip.output_path ? '' : 'opacity-60'}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-semibold truncate">{clip.title}</p>
                      {clip.hook && (
                        <p className="text-xs text-dark-400 mt-1 line-clamp-2">« {clip.hook} »</p>
                      )}
                    </div>
                    <span className="shrink-0 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-accent-500/15 text-accent-300 border border-accent-500/30">
                      <Sparkles className="w-3 h-3" /> {clip.score}
                    </span>
                  </div>
                  <p className="text-xs text-dark-500 mt-2 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatDuration(clip.duration_s)}
                    {typeof clip.size_bytes === 'number' && clip.size_bytes > 0 &&
                      ` · ${(clip.size_bytes / (1024 * 1024)).toFixed(1)} MB`}
                    {' · MP4 vertical 9:16'}
                  </p>
                  {clip.error && (
                    <p className="text-xs text-red-400 mt-2">
                      Échec du montage de ce clip. Les autres restent disponibles.
                    </p>
                  )}
                  {clip.output_path && renderJobId && (
                    <div className="flex gap-2 mt-3">
                      <button onClick={() => setPreviewClip(clip.index)}
                        className="btn-secondary !py-1.5 !px-3 text-sm flex items-center gap-1.5">
                        <Play className="w-3.5 h-3.5" /> Aperçu
                      </button>
                      <button onClick={() => downloadClip(renderJobId, clip.index)}
                        className="btn-primary !py-1.5 !px-3 text-sm flex items-center gap-1.5">
                        <Download className="w-3.5 h-3.5" /> Télécharger
                      </button>
                      <button
                        onClick={() => {
                          navigator.clipboard?.writeText(`${clip.title}\n${clip.hook ?? ''}`.trim())
                          toast('info', 'Titre + hook copiés')
                        }}
                        className="text-dark-500 hover:text-white text-xs">
                        Copier titre
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <button onClick={reset} className="btn-secondary">
            Transformer une autre vidéo
          </button>
        </div>
      )}
    </div>
  )
}
