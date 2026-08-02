import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Zap, VolumeX, Sparkles, Loader2, ArrowLeft, ChevronLeft, ChevronRight,
  Image as ImageIcon, Music, Subtitles, Smartphone, Megaphone, PenTool, Check,
} from 'lucide-react'
import VideoPlayer from '../components/video/VideoPlayer'
import Timeline from '../components/video/Timeline'
import JobProgress from '../components/video/JobProgress'
import Surface from '../components/ui/Surface'
import Toggle from '../components/ui/Toggle'
import { getVideo, getStreamUrl } from '../api/videos'
import {
  getJobDownloadUrl,
  createJob,
  listJobs,
  listModesFull,
  type JobOptions,
  type ModeDescriptor,
  type ModeFamily,
  type PipelineVersion,
} from '../api/jobs'
import { toast } from '../components/ui/Toast'

type EditMode = string

interface VideoMeta {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
}

// Repli statique si `GET /jobs/modes` est indisponible. La source de vérité est
// le backend (`app/api/v1/modes.py`) : on ne garde ici que les moteurs phares,
// dans le même ordre, pour que l'écran reste utilisable hors ligne.
const FALLBACK_FAMILIES: ModeFamily[] = [
  { id: 'collage', label: 'Collage papier', hint: 'Assemblage éditorial animé' },
  { id: 'viral', label: 'Styles viraux', hint: 'Sous-titres et motion design' },
]

const FALLBACK_MODES: ModeDescriptor[] = [
  {
    id: 'collage_premium',
    name: 'Collage Premium',
    icon: '✂️',
    family: 'collage',
    badge: 'images IA si dispo',
    description:
      'Analyse du sens, métaphore visuelle et collage papier éditorial assemblé ' +
      'pièce par pièce à l’écran.',
    pipeline: 'v2',
    default: true,
    defaults: {
      remove_silence: true, dynamic_captions: true, ai_broll: true,
      motion_design: true, music: true, sfx: true, vertical_9_16: true,
      final_cta: true, visual_mode: 'auto_fallback',
      subtitle_template: 'pill_editorial',
      collage_broll: true, collage_profile: 'editorial',
      broll_style: 'tiktok_viral', broll_demographic: 'african',
    },
  },
  {
    id: 'collage_ugc_product',
    name: 'Collage UGC Produit',
    icon: '📦',
    family: 'collage',
    badge: '0 crédit image',
    description:
      'Pour présenter un produit face caméra : le collage papier illustre le prix, ' +
      'la livraison, la texture, le résultat. Aucune image IA générée.',
    pipeline: 'v2',
    defaults: {
      remove_silence: true, dynamic_captions: true, ai_broll: true,
      motion_design: false, music: true, sfx: true, vertical_9_16: true,
      final_cta: true, visual_mode: 'credit_saver',
      subtitle_template: 'pill_editorial',
      collage_broll: true, collage_profile: 'ugc_product',
      broll_style: 'tiktok_viral', broll_demographic: 'african',
    },
  },
  {
    id: 'collage_ugc_motion',
    name: 'Collage UGC Produit + Motion',
    icon: '🎞️',
    family: 'collage',
    badge: '0 crédit image',
    description:
      'Le moteur UGC Produit avec les scènes de motion design animées. ' +
      'Toujours aucune image IA générée.',
    pipeline: 'v2',
    defaults: {
      remove_silence: true, dynamic_captions: true, ai_broll: true,
      motion_design: true, music: true, sfx: true, vertical_9_16: true,
      final_cta: true, visual_mode: 'credit_saver',
      subtitle_template: 'pill_editorial',
      collage_broll: true, collage_profile: 'ugc_motion',
      broll_style: 'tiktok_viral', broll_demographic: 'african',
    },
  },
  {
    id: 'signature_3d',
    name: 'Signature 3D',
    icon: '✨',
    family: 'viral',
    badge: 'images IA si dispo',
    description:
      'Illustrations 3D uniques par vidéo, scènes motion design variées, ' +
      'sous-titres karaoké jaunes, SFX et transitions lumineuses.',
    pipeline: 'v2',
    defaults: {
      remove_silence: true, dynamic_captions: true, ai_broll: true,
      motion_design: true, music: true, sfx: true, vertical_9_16: true,
      final_cta: true, visual_mode: 'auto_fallback',
      subtitle_template: 'tiktok_yellow',
      broll_style: 'tiktok_viral', broll_demographic: 'african',
    },
  },
  {
    id: 'credit_saver_creator_edit',
    name: 'Économique',
    icon: '⚡',
    family: 'viral',
    badge: '0 crédit image',
    description:
      'Silences coupés, captions, zooms, SFX, transitions et motion design ' +
      'procédural — aucune image IA payante.',
    pipeline: 'v2',
    defaults: {
      remove_silence: true, dynamic_captions: true, ai_broll: false,
      motion_design: true, music: true, sfx: true, vertical_9_16: true,
      final_cta: true, visual_mode: 'credit_saver',
      broll_style: 'tiktok_viral', broll_demographic: 'african',
    },
  },
]

interface Scenes {
  scenes: { start: number; end: number; duration: number }[]
}

function isScenes(value: unknown): value is Scenes {
  if (!value || typeof value !== 'object') return false
  const v = value as { scenes?: unknown }
  return Array.isArray(v.scenes)
}

export default function Editor() {
  const { videoId } = useParams<{ videoId: string }>()
  const navigate = useNavigate()
  const [video, setVideo] = useState<VideoMeta | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [modes, setModes] = useState<ModeDescriptor[]>(FALLBACK_MODES)
  const [families, setFamilies] = useState<ModeFamily[]>(FALLBACK_FAMILIES)
  const [activeFamily, setActiveFamily] = useState<string>('collage')
  const [selectedMode, setSelectedMode] = useState<EditMode>(FALLBACK_MODES[0].id)
  const [processing, setProcessing] = useState(false)
  const [completedResult, setCompletedResult] = useState<Record<string, unknown> | null>(null)
  const [loadError, setLoadError] = useState('')
  const [pipelineVersion, setPipelineVersion] = useState<PipelineVersion>('v2')
  const [options, setOptions] = useState<JobOptions>(FALLBACK_MODES[0].defaults)
  const [ctaText, setCtaText] = useState('')
  const [logoText, setLogoText] = useState('')

  // Charge le catalogue de modes depuis l'API (DRY avec le backend).
  useEffect(() => {
    let cancelled = false
    listModesFull()
      .then(({ modes: list, default_mode, families: fams }) => {
        if (cancelled || list.length === 0) return
        setModes(list)
        if (fams.length) setFamilies(fams)
        const preferred =
          list.find((m) => m.id === default_mode) ??
          list.find((m) => m.default) ??
          list[0]
        setSelectedMode(preferred.id)
        setActiveFamily(preferred.family ?? 'collage')
      })
      .catch(() => { /* on garde le fallback */ })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const mode = modes.find((m) => m.id === selectedMode)
    if (mode) {
      setOptions(mode.defaults)
      setPipelineVersion(mode.pipeline)
    }
  }, [selectedMode, modes])

  useEffect(() => {
    if (!videoId) return
    let cancelled = false

    async function load() {
      try {
        const [videoData, jobs] = await Promise.all([
          getVideo(videoId!),
          listJobs(videoId!),
        ])
        if (cancelled) return
        setVideo(videoData)
        const activeJob = jobs.find(
          (j: { status: string }) => j.status === 'processing' || j.status === 'pending',
        )
        if (activeJob) {
          // Un NOUVEAU montage est en cours : on le suit, lui — l'ancien
          // montage terminé ne doit JAMAIS reprendre l'écran.
          setActiveJobId(activeJob.id)
          setProcessing(true)
        } else {
          const completed = jobs.find((j: { status: string }) => j.status === 'completed')
          if (completed?.result) {
            setCompletedResult(completed.result)
            setActiveJobId(completed.id)
            setProcessing(false)
          }
        }
      } catch {
        if (!cancelled) setLoadError('Impossible de charger la vidéo')
      }
    }
    load()
    return () => { cancelled = true }
  }, [videoId])

  const toggle = (key: keyof JobOptions) => () => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleAutoEdit = useCallback(async () => {
    if (!videoId) return
    setProcessing(true)
    // CRITIQUE: ne JAMAIS laisser l'ancien montage s'afficher pendant qu'un
    // nouveau se forge — c'est ce qui faisait croire que rien n'avait changé.
    setCompletedResult(null)
    try {
      const payloadOptions: JobOptions = {
        ...options,
        cta_text: ctaText.trim() || undefined,
        logo_text: logoText.trim() || undefined,
      }
      const job = await createJob({
        video_id: videoId,
        job_type: 'pipeline',
        mode: selectedMode,
        pipeline_version: pipelineVersion,
        options: payloadOptions,
      })
      setActiveJobId(job.id)
      toast('info', `Montage lancé : ${modes.find((m) => m.id === selectedMode)?.name ?? selectedMode}`)
    } catch (err: unknown) {
      setProcessing(false)
      let msg = 'Impossible de démarrer le traitement'
      if (err && typeof err === 'object' && 'response' in err) {
        msg =
          (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || msg
      }
      toast('error', msg)
    }
  }, [videoId, selectedMode, options, ctaText, logoText, pipelineVersion, modes])

  const handleJobComplete = useCallback(
    (result: Record<string, unknown>) => {
      setCompletedResult(result)
      setProcessing(false)
      if (videoId) getVideo(videoId).then(setVideo).catch(() => { /* noop */ })
    },
    [videoId],
  )

  const handleRetry = useCallback(() => {
    setActiveJobId(null)
    setProcessing(false)
    handleAutoEdit()
  }, [handleAutoEdit])

  const handleJobCancelled = useCallback(() => {
    setActiveJobId(null)
    setProcessing(false)
  }, [])

  const visibleFamilies = useMemo(
    () => families.filter((f) => modes.some((m) => (m.family ?? 'viral') === f.id)),
    [families, modes],
  )
  const visibleModes = useMemo(
    () => modes.filter((m) => (m.family ?? 'viral') === activeFamily),
    [modes, activeFamily],
  )
  const currentMode = modes.find((m) => m.id === selectedMode)

  if (loadError) {
    return (
      <div className="mx-auto max-w-md py-20 text-center shell-gutter">
        <p className="mb-5 text-sm text-red-300">{loadError}</p>
        <button onClick={() => navigate('/dashboard')} className="btn-secondary text-sm">
          Retour au studio
        </button>
      </div>
    )
  }

  if (!video) {
    return (
      <div className="mx-auto max-w-[1600px] space-y-5 py-8 shell-gutter" aria-busy>
        <div className="skeleton h-10 w-72" />
        <div className="skeleton h-40 w-full" />
        <div className="grid gap-5 lg:grid-cols-12">
          <div className="skeleton h-[420px] lg:col-span-7 xl:col-span-8" />
          <div className="skeleton h-[420px] lg:col-span-5 xl:col-span-4" />
        </div>
      </div>
    )
  }

  const scenes = isScenes(completedResult?.scenes) ? completedResult!.scenes as Scenes : undefined
  const previewSrc = activeJobId && completedResult
    ? getJobDownloadUrl(activeJobId)
    : getStreamUrl(videoId!)
  const notice = fallbackNotice(completedResult)

  return (
    <div className="pb-10">
      {/* ---------------------------------------------------------------- */}
      {/* Barre d'action COLLANTE : le bouton de lancement reste visible en  */}
      {/* permanence. Avant, il vivait au bas d'une colonne latérale et il   */}
      {/* fallait faire défiler tout l'écran pour lancer un montage.         */}
      {/* Elle se colle SOUS l'en-tête de la coquille (64 px), sinon les     */}
      {/* deux se chevauchent au défilement.                                 */}
      {/* ---------------------------------------------------------------- */}
      <div className="sticky top-16 z-20 border-b border-white/[0.06] bg-surface-canvas/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 py-3 shell-gutter sm:gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-white/[0.08] text-dark-400 transition-colors hover:border-white/25 hover:text-white"
            aria-label="Retour au studio"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-[15px] font-semibold leading-tight sm:text-base">
              {video.title}
            </h1>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-dark-500">
              <span className="tabular-nums">{(video.size_bytes / (1024 * 1024)).toFixed(1)} Mo</span>
              {video.duration_s != null && (
                <>
                  <span aria-hidden>·</span>
                  <span className="tabular-nums">{formatDuration(video.duration_s)}</span>
                </>
              )}
              {currentMode && (
                <>
                  <span aria-hidden>·</span>
                  <span className="truncate text-dark-300">
                    {currentMode.icon} {currentMode.name}
                  </span>
                </>
              )}
            </p>
          </div>

          <button
            onClick={handleAutoEdit}
            disabled={processing}
            className="btn-accent flex shrink-0 items-center justify-center gap-2 !px-4 !py-2.5 text-sm sm:!px-7"
          >
            {processing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="hidden sm:inline">Montage en cours…</span>
                <span className="sm:hidden">En cours…</span>
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" />
                <span className="hidden sm:inline">Forger le montage</span>
                <span className="sm:hidden">Forger</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-[1600px] shell-gutter">
        {/* -------------------------------------------------------------- */}
        {/* Sélecteur de moteur — HORIZONTAL. Les moteurs étaient empilés    */}
        {/* verticalement dans une colonne étroite : la liste s'allongeait à */}
        {/* chaque nouveau moteur et poussait le reste de l'écran vers le    */}
        {/* bas. Ici, familles en onglets + rail qui défile latéralement.    */}
        {/* -------------------------------------------------------------- */}
        <section className="pt-7">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="eyebrow">Moteur de montage</p>
              <p className="mt-1.5 text-sm text-dark-400">
                {visibleFamilies.find((f) => f.id === activeFamily)?.hint ??
                  'Choisis la direction artistique du rendu'}
              </p>
            </div>

            {/* Onglets de famille: l'indicateur GLISSE d'un onglet à l'autre
                au lieu de clignoter — on suit des yeux où on vient d'aller. */}
            <div className="flex flex-wrap gap-1 rounded-xl border border-white/[0.07] bg-white/[0.025] p-1">
              {visibleFamilies.map((family) => (
                <button
                  key={family.id}
                  onClick={() => setActiveFamily(family.id)}
                  aria-pressed={activeFamily === family.id}
                  className={`relative rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors duration-200 ${
                    activeFamily === family.id ? 'text-white' : 'text-dark-500 hover:text-dark-200'
                  }`}
                >
                  {activeFamily === family.id && (
                    <motion.span
                      layoutId="family-tab"
                      className="absolute inset-0 rounded-lg border border-primary-500/35 bg-primary-500/15"
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                    />
                  )}
                  <span className="relative">{family.label}</span>
                </button>
              ))}
            </div>
          </div>

          <EngineRail
            modes={visibleModes}
            selectedId={selectedMode}
            onSelect={setSelectedMode}
          />
        </section>

        {/* -------------------------------------------------------------- */}
        {/* Aperçu + réglages, côte à côte                                   */}
        {/* -------------------------------------------------------------- */}
        <div className="mt-6 grid gap-5 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-7 xl:col-span-8">
            {completedResult && (
              <Note tone="ok">
                Aperçu du dernier montage terminé. Relancer un montage masque cet
                aperçu jusqu'à la fin du nouveau rendu.
              </Note>
            )}
            {notice && <Note tone="warn">{notice}</Note>}

            <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-black shadow-e3">
              <VideoPlayer src={previewSrc} />
            </div>

            {scenes && scenes.scenes.length > 0 && (
              <Timeline scenes={scenes.scenes} totalDuration={video.duration_s || 0} />
            )}

            {activeJobId && (processing || completedResult) && (
              <JobProgress
                jobId={activeJobId}
                onComplete={handleJobComplete}
                onRetry={handleRetry}
                onCancelled={handleJobCancelled}
              />
            )}

            {!!completedResult?.montage && (
              <MontageRecap
                montage={completedResult.montage as Record<string, unknown>}
                aiImagesSkipped={completedResult.aiImagesSkipped === true}
                motionRequested={!!options.motion_design}
              />
            )}

            {!!completedResult?.transcription && (
              <Surface>
                <h3 className="mb-2.5 text-sm font-semibold">Transcription</h3>
                <p className="max-h-40 overflow-y-auto pr-2 text-sm leading-relaxed text-dark-400">
                  {typeof (completedResult.transcription as { text?: unknown }).text === 'string'
                    ? (completedResult.transcription as { text: string }).text
                    : ''}
                </p>
              </Surface>
            )}
          </div>

          {/* Réglages : interrupteurs compacts sur deux colonnes plutôt qu'une
              liste de cases à cocher empilées. */}
          <aside className="space-y-4 lg:col-span-5 xl:col-span-4">
            <Surface>
              <h3 className="mb-3.5 text-sm font-semibold">Options du montage</h3>
              <div className="grid grid-cols-2 gap-2">
                <Toggle
                  icon={<VolumeX className="h-4 w-4" />}
                  label="Silences coupés"
                  checked={!!options.remove_silence}
                  onToggle={toggle('remove_silence')}
                />
                <Toggle
                  icon={<Subtitles className="h-4 w-4" />}
                  label="Sous-titres"
                  checked={!!options.dynamic_captions}
                  onToggle={toggle('dynamic_captions')}
                />
                <Toggle
                  icon={<PenTool className="h-4 w-4" />}
                  label="Motion design"
                  checked={!!options.motion_design}
                  onToggle={toggle('motion_design')}
                />
                <Toggle
                  icon={<ImageIcon className="h-4 w-4" />}
                  label="Illustrations"
                  checked={!!options.ai_broll}
                  onToggle={toggle('ai_broll')}
                />
                <Toggle
                  icon={<Music className="h-4 w-4" />}
                  label="Musique"
                  checked={!!options.music}
                  onToggle={toggle('music')}
                />
                <Toggle
                  icon={<Sparkles className="h-4 w-4" />}
                  label="Effets sonores"
                  checked={!!options.sfx}
                  onToggle={toggle('sfx')}
                />
                <Toggle
                  icon={<Smartphone className="h-4 w-4" />}
                  label="Vertical 9:16"
                  checked={!!options.vertical_9_16}
                  onToggle={toggle('vertical_9_16')}
                />
                <Toggle
                  icon={<Megaphone className="h-4 w-4" />}
                  label="CTA final"
                  checked={!!options.final_cta}
                  onToggle={toggle('final_cta')}
                />
              </div>

              {options.visual_mode === 'credit_saver' && (
                <p className="mt-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.07] px-3 py-2.5 text-xs leading-relaxed text-emerald-300/90">
                  Ce moteur n'appelle aucune API d'image&nbsp;: les illustrations sont
                  découpées par CutForge. Coût de génération nul.
                </p>
              )}

              {options.ai_broll && options.visual_mode !== 'credit_saver' && (
                <div className="mt-3.5">
                  <label className="mb-1.5 block text-xs text-dark-400" htmlFor="demographic">
                    Personnes dans les images générées
                  </label>
                  <select
                    id="demographic"
                    value={options.broll_demographic || 'african'}
                    onChange={(e) => setOptions((prev) => ({
                      ...prev,
                      broll_demographic: e.target.value as JobOptions['broll_demographic'],
                    }))}
                    className="field text-sm"
                  >
                    <option value="african">Africains / Afrique (défaut)</option>
                    <option value="caucasian">Blancs / caucasiens</option>
                    <option value="global">Mixte international</option>
                  </select>
                </div>
              )}
            </Surface>

            <details className="panel group !p-0">
              <summary className="flex cursor-pointer list-none items-center justify-between p-5 text-sm font-semibold sm:p-6">
                Branding
                <span className="flex items-center gap-2 text-xs font-normal text-dark-500">
                  <span className="group-open:hidden">optionnel</span>
                  <ChevronRight className="h-4 w-4 transition-transform duration-300 ease-premium group-open:rotate-90" />
                </span>
              </summary>
              <div className="space-y-3 px-5 pb-5 sm:px-6 sm:pb-6">
                <div>
                  <label className="mb-1.5 block text-xs text-dark-400" htmlFor="logo-text">
                    Texte intro / logo
                  </label>
                  <input
                    id="logo-text"
                    type="text"
                    maxLength={60}
                    value={logoText}
                    onChange={(e) => setLogoText(e.target.value)}
                    placeholder="Ex. Lance ton e-commerce"
                    className="field text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs text-dark-400" htmlFor="cta-text">
                    Texte du CTA final
                  </label>
                  <input
                    id="cta-text"
                    type="text"
                    maxLength={120}
                    value={ctaText}
                    onChange={(e) => setCtaText(e.target.value)}
                    placeholder="Ex. Abonne-toi 🔔"
                    className="field text-sm"
                  />
                </div>
              </div>
            </details>

            {Array.isArray(completedResult?.steps_completed) && (
              <Surface>
                <h3 className="mb-3 text-sm font-semibold">Résumé technique</h3>
                <div className="flex flex-wrap gap-1.5">
                  {(completedResult!.steps_completed as string[]).map((step) => (
                    <span
                      key={step}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.08] px-2 py-1 text-[11px] text-emerald-300"
                    >
                      <Check className="h-3 w-3" strokeWidth={3} />
                      {step.replace(/_/g, ' ')}
                    </span>
                  ))}
                  {Array.isArray(completedResult?.steps_failed) &&
                    (completedResult!.steps_failed as string[]).map((step) => (
                      <span
                        key={step}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-red-400/20 bg-red-400/[0.08] px-2 py-1 text-[11px] text-red-300"
                      >
                        ✕ {step.replace(/_/g, ' ')}
                      </span>
                    ))}
                </div>
              </Surface>
            )}
          </aside>
        </div>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Bandeau d'information non bloquant                                          */
/* -------------------------------------------------------------------------- */
function Note({ tone, children }: { tone: 'ok' | 'warn'; children: React.ReactNode }) {
  const tones = {
    ok: 'border-emerald-500/22 bg-emerald-500/[0.08] text-emerald-200',
    warn: 'border-amber-500/22 bg-amber-500/[0.08] text-amber-200',
  }
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm leading-relaxed ${tones[tone]}`}>
      {tone === 'ok'
        ? <Check className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2.5} />
        : <Zap className="mt-0.5 h-4 w-4 shrink-0" />}
      <span>{children}</span>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Rail horizontal des moteurs                                                 */
/* -------------------------------------------------------------------------- */
function EngineRail(props: {
  modes: ModeDescriptor[]
  selectedId: string
  onSelect: (id: string) => void
}) {
  const railRef = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ start: false, end: false })

  const syncEdges = useCallback(() => {
    const el = railRef.current
    if (!el) return
    // 2 px de tolérance : les navigateurs arrondissent scrollLeft.
    setEdges({
      start: el.scrollLeft > 2,
      end: el.scrollLeft + el.clientWidth < el.scrollWidth - 2,
    })
  }, [])

  useEffect(() => {
    syncEdges()
    const el = railRef.current
    if (!el) return
    const observer = new ResizeObserver(syncEdges)
    observer.observe(el)
    return () => observer.disconnect()
  }, [syncEdges, props.modes])

  const scrollBy = (direction: 1 | -1) => {
    const el = railRef.current
    if (!el) return
    el.scrollBy({ left: direction * Math.round(el.clientWidth * 0.8), behavior: 'smooth' })
  }

  return (
    <div className="relative">
      <div
        ref={railRef}
        onScroll={syncEdges}
        className="no-scrollbar flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth pb-1"
      >
        {props.modes.map((mode) => {
          const selected = mode.id === props.selectedId
          return (
            <button
              key={mode.id}
              onClick={() => props.onSelect(mode.id)}
              aria-pressed={selected}
              // `flex-1` + `basis` : quand la famille tient dans la largeur, les
              // cartes s'étalent au lieu de laisser un vide à droite; dès qu'il
              // y en a trop, elles gardent leur largeur mini et le rail défile.
              className={`group relative min-w-[16.5rem] flex-1 basis-[17rem] snap-start overflow-hidden rounded-2xl border p-4 text-left transition-all duration-400 ease-premium ${
                selected
                  ? 'border-primary-500/50 bg-primary-500/[0.10] shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_22px_50px_-26px_rgba(63,114,255,0.95)]'
                  : 'border-white/[0.07] bg-white/[0.025] shadow-e1 hover:-translate-y-[3px] hover:border-white/20 hover:shadow-e3'
              }`}
            >
              {/* Liseré de marque sur la carte sélectionnée: il rend le choix
                  lisible d'un coup d'œil même sur un rail qui défile. */}
              {selected && (
                <motion.span
                  layoutId="engine-edge"
                  className="absolute inset-x-0 top-0 h-[2px] bg-brand-sweep"
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                />
              )}

              <div className="flex items-start justify-between gap-2">
                <span className="text-[26px] leading-none">{mode.icon}</span>
                <span
                  className={`grid h-5 w-5 place-items-center rounded-full transition-all duration-300 ${
                    selected
                      ? 'scale-100 bg-primary-500 text-white'
                      : 'scale-90 border border-white/12 text-transparent'
                  }`}
                >
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
              </div>

              <p className="mt-3 font-display text-[15px] font-semibold leading-snug">
                {mode.name}
              </p>

              <div className="mt-2 flex flex-wrap gap-1.5">
                {mode.badge && (
                  <span
                    className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                      mode.badge.startsWith('0')
                        ? 'bg-emerald-400/14 text-emerald-300'
                        : 'bg-white/[0.07] text-dark-400'
                    }`}
                  >
                    {mode.badge}
                  </span>
                )}
                {mode.pipeline !== 'v2' && (
                  <span className="rounded-md bg-white/[0.07] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-dark-500">
                    ancien moteur
                  </span>
                )}
              </div>

              <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-dark-500">
                {mode.description}
              </p>
            </button>
          )
        })}
      </div>

      {edges.start && <RailArrow side="left" onClick={() => scrollBy(-1)} />}
      {edges.end && <RailArrow side="right" onClick={() => scrollBy(1)} />}
    </div>
  )
}

function RailArrow(props: { side: 'left' | 'right'; onClick: () => void }) {
  const Icon = props.side === 'left' ? ChevronLeft : ChevronRight
  return (
    <button
      onClick={props.onClick}
      aria-label={props.side === 'left' ? 'Moteurs précédents' : 'Moteurs suivants'}
      className={`absolute top-1/2 hidden -translate-y-1/2 rounded-full border border-white/15 bg-dark-900/90 p-2 text-white shadow-lg backdrop-blur transition-colors hover:border-white/40 sm:grid ${
        props.side === 'left' ? '-left-3' : '-right-3'
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  )
}

/* -------------------------------------------------------------------------- */
/* Récapitulatif du montage produit                                            */
/* -------------------------------------------------------------------------- */
function MontageRecap(props: {
  montage: Record<string, unknown>
  aiImagesSkipped: boolean
  motionRequested: boolean
}) {
  const n = (key: string) => Number(props.montage[key] ?? 0)
  const removed = Number(props.montage.removed_duration_s ?? 0)
  const source = Number(props.montage.source_duration_s ?? 0)
  const percent = source > 0 ? Math.round((removed / source) * 100) : 0

  // En mode économique, l'absence d'images IA est NORMALE : elle ne doit pas
  // s'afficher comme une anomalie.
  const items: Array<[string, string, boolean]> = [
    ['⚡', `${n('key_moment_punches')} punch-zooms`, n('key_moment_punches') > 0],
    ['💡', `${n('light_overlays')} passages de lumière`, n('light_overlays') > 0],
    ['🎨', `${n('motion_scenes_rendered')} scènes motion design`, n('motion_scenes_rendered') > 0],
    ['✂️', `${n('collage_clips')} scènes de collage`, n('collage_clips') > 0],
    ['🔊', `${n('sfx_cues')} effets sonores`, n('sfx_cues') > 0],
    ['🏷️', `${n('keyword_popups')} mots-clés popup`, n('keyword_popups') > 0],
    [
      '🖼️',
      n('broll_images') > 0
        ? `${n('broll_images')} images B-roll IA`
        : 'Images IA non requises',
      n('broll_images') > 0 || props.aiImagesSkipped,
    ],
  ]

  return (
    <Surface>
      <h3 className="mb-3.5 text-sm font-semibold">Contenu du montage</h3>

      {/* La découpe est LE chiffre du produit: il mérite sa propre tuile, pas
          une ligne de texte perdue au milieu des autres. */}
      {source > 0 && (
        <div className="mb-4 flex items-center gap-4 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
          <div>
            <p className="font-display text-2xl font-bold leading-none tabular-nums text-white">
              −{removed.toFixed(0)}<span className="ml-0.5 text-base text-dark-500">s</span>
            </p>
            <p className="mt-1.5 text-[11px] text-dark-500">retirés sur {source.toFixed(0)} s</p>
          </div>
          <div className="min-w-0 flex-1">
            <div className="bar-track h-1.5">
              <div className="bar-fill" style={{ width: `${Math.min(100, percent)}%` }} />
            </div>
            <p className="mt-2 text-xs leading-relaxed text-dark-400">
              Silences, hésitations et répétitions coupés
              {percent > 0 ? ` — vidéo ${percent} % plus courte.` : '.'}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2">
        {items.map(([icon, label, ok]) => (
          <div
            key={label}
            className={`flex items-center gap-2.5 rounded-xl border px-3 py-2.5 ${
              ok
                ? 'border-white/[0.07] bg-white/[0.03] text-dark-100'
                : 'border-red-400/18 bg-red-400/[0.06] text-red-300'
            }`}
          >
            <span className="text-sm">{icon}</span>
            <span className="text-xs font-medium">{label}</span>
          </div>
        ))}
      </div>

      {props.motionRequested && n('motion_scenes_rendered') === 0 && (
        <p className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/[0.08] p-3 text-xs leading-relaxed text-amber-300">
          Aucune scène motion design dans ce rendu — le reste du montage
          (punch-zooms, SFX, captions) est bien présent.
        </p>
      )}
    </Surface>
  )
}

/* -------------------------------------------------------------------------- */
function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// Messages d'explication NON bloquants pour les raisons de fallback côté moteur.
const FALLBACK_REASON_LABELS: Record<string, string> = {
  insufficient_credits: 'crédits images IA épuisés',
  payment_required: 'paiement requis pour les images IA',
  quota_exceeded: 'quota images IA dépassé',
  rate_limited: 'API images IA temporairement saturée',
  timeout: "délai dépassé sur l'API images IA",
  provider_unavailable: "fournisseur d'images IA indisponible",
  missing_api_key: 'clé API images non configurée',
  disabled: 'génération payante désactivée',
  image_generation_failed: 'génération des images IA en échec',
}

/**
 * Renvoie un message NON bloquant quand le rendu a continué sans images IA,
 * ou null s'il n'y a rien à signaler (mode économique explicite, ou images
 * bien générées). Ne s'affiche jamais comme une erreur rouge.
 */
function fallbackNotice(result: Record<string, unknown> | null): string | null {
  if (!result) return null
  const reason = result.fallbackReason
  if (!reason || typeof reason !== 'string') return null
  const detail = FALLBACK_REASON_LABELS[reason] ?? reason.replace(/_/g, ' ')
  return `Les images IA sont indisponibles (${detail}). Le montage a continué en mode économique : punch-zooms, SFX, captions et motion design.`
}
