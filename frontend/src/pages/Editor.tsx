import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Zap, Mic, VolumeX, Film, Sparkles, Loader2, ArrowLeft,
  Image as ImageIcon, Music, Subtitles, Smartphone, Megaphone, PenTool,
} from 'lucide-react'
import VideoPlayer from '../components/video/VideoPlayer'
import Timeline from '../components/video/Timeline'
import JobProgress from '../components/video/JobProgress'
import { getVideo, getStreamUrl } from '../api/videos'
import {
  getJobDownloadUrl,
  createJob,
  listJobs,
  listModes,
  type JobOptions,
  type ModeDescriptor,
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

// Fallback statique utilise si l'endpoint /jobs/modes est indisponible.
const FALLBACK_MODES: ModeDescriptor[] = [
  {
    id: 'business_premium_african',
    name: 'Business premium 🇸🇳🇨🇮🇹🇬',
    icon: '💼',
    description: 'Style africain moderne, B-roll premium, musique sobre',
    pipeline: 'v2',
    defaults: {
      remove_silence: true, dynamic_captions: true, ai_broll: true,
      motion_design: true,
      music: true, sfx: false, vertical_9_16: true, final_cta: true,
      broll_style: 'african_business_premium',
      broll_demographic: 'african',
    },
  },
]

const PIPELINE_LABEL: Record<PipelineVersion, string> = {
  v1: 'Pipeline classique',
  v2: 'Pipeline IA V2 (B-roll africain)',
}

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
    listModes()
      .then((list) => {
        if (cancelled || list.length === 0) return
        setModes(list)
        // Selectionne par defaut le premier mode v2 (business premium africain)
        const preferred = list.find((m) => m.pipeline === 'v2') ?? list[0]
        setSelectedMode(preferred.id)
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
          setActiveJobId(activeJob.id)
          setProcessing(true)
        }
        const completed = jobs.find((j: { status: string }) => j.status === 'completed')
        if (completed?.result) {
          setCompletedResult(completed.result)
          setActiveJobId(completed.id)
          setProcessing(false)
        }
      } catch {
        if (!cancelled) setLoadError('Impossible de charger la vidéo')
      }
    }
    load()
    return () => { cancelled = true }
  }, [videoId])

  const toggle = (key: keyof JobOptions) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setOptions((prev) => ({ ...prev, [key]: e.target.checked }))
  }

  const handleAutoEdit = useCallback(async () => {
    if (!videoId) return
    setProcessing(true)
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
      toast('info', `Traitement lancé : ${modes.find((m) => m.id === selectedMode)?.name ?? selectedMode}`)
    } catch (err: unknown) {
      setProcessing(false)
      let msg = 'Impossible de démarrer le traitement'
      if (err && typeof err === 'object' && 'response' in err) {
        msg =
          (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || msg
      }
      toast('error', msg)
    }
  }, [videoId, selectedMode, options, ctaText, logoText, pipelineVersion])

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

  if (loadError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center">
        <p className="text-red-400 mb-4">{loadError}</p>
        <button onClick={() => navigate('/dashboard')} className="btn-secondary">
          Retour au dashboard
        </button>
      </div>
    )
  }

  if (!video) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    )
  }

  const scenes = isScenes(completedResult?.scenes) ? completedResult!.scenes as Scenes : undefined
  const previewSrc = activeJobId && completedResult
    ? getJobDownloadUrl(activeJobId)
    : getStreamUrl(videoId!)

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-dark-400 hover:text-white transition-colors"
          aria-label="Retour au dashboard"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{video.title}</h1>
          <p className="text-dark-400 text-sm">
            {video.status}
            {' · '}
            {(video.size_bytes / (1024 * 1024)).toFixed(1)} MB
            {video.duration_s != null && (
              ` · ${Math.floor(video.duration_s / 60)}:${Math.floor(video.duration_s % 60).toString().padStart(2, '0')}`
            )}
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {completedResult && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
              Aperçu du montage final généré. Tu peux le lire ici ou utiliser le bouton Download Video.
            </div>
          )}
          <VideoPlayer src={previewSrc} />
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
        </div>

        <div className="space-y-4">
          {/* Pipeline version */}
          <div className="card">
            <h3 className="font-semibold mb-3">Moteur</h3>
            <div className="flex gap-2">
              {(['v2', 'v1'] as PipelineVersion[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setPipelineVersion(v)}
                  className={`flex-1 px-3 py-2 rounded-lg border text-sm transition ${
                    pipelineVersion === v
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-dark-700 hover:border-dark-500'
                  }`}
                >
                  {PIPELINE_LABEL[v]}
                </button>
              ))}
            </div>
            <p className="text-xs text-dark-400 mt-2">
              V2 ajoute le B-roll IA orienté Afrique francophone, captions dynamiques et CTA.
            </p>
          </div>

          {/* Mode */}
          <div className="card">
            <h3 className="font-semibold mb-3">Style de montage</h3>
            <div className="space-y-2">
              {modes.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all text-left ${
                    selectedMode === mode.id
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-dark-700 hover:border-dark-500'
                  }`}
                >
                  <span className="text-2xl">{mode.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium flex items-center gap-2">
                      <span className="truncate">{mode.name}</span>
                      <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded ${
                        mode.pipeline === 'v2'
                          ? 'bg-primary-500/20 text-primary-300'
                          : 'bg-dark-700 text-dark-300'
                      }`}>
                        {mode.pipeline}
                      </span>
                    </p>
                    <p className="text-xs text-dark-400">{mode.description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Toggles */}
          <div className="card">
            <h3 className="font-semibold mb-3">Options</h3>
            <ToggleRow
              icon={<VolumeX className="w-4 h-4 text-primary-400" />}
              label="Supprimer les silences"
              checked={!!options.remove_silence}
              onChange={toggle('remove_silence')}
            />
            <ToggleRow
              icon={<Subtitles className="w-4 h-4 text-primary-400" />}
              label="Sous-titres dynamiques"
              checked={!!options.dynamic_captions}
              onChange={toggle('dynamic_captions')}
            />
            <ToggleRow
              icon={<ImageIcon className="w-4 h-4 text-primary-400" />}
              label="B-roll IA"
              checked={!!options.ai_broll}
              onChange={toggle('ai_broll')}
            />

            <ToggleRow
              icon={<PenTool className="w-4 h-4 text-primary-400" />}
              label="Motion design illustré"
              checked={!!options.motion_design}
              onChange={toggle('motion_design')}
            />
            {options.motion_design && (
              <p className="text-xs text-dark-500 -mt-1 mb-2 pl-6">
                Les moments clés du discours sont illustrés par des dessins animés
                (flèches, étapes, chiffres) avec transitions et effets sonores.
              </p>
            )}

            {options.ai_broll && (
              <div className="mt-3">
                <label className="text-xs text-dark-400 block mb-1">Personnes pour les images B-roll</label>
                <select
                  value={options.broll_demographic || 'african'}
                  onChange={(e) => setOptions((prev) => ({
                    ...prev,
                    broll_demographic: e.target.value as JobOptions['broll_demographic'],
                  }))}
                  className="w-full bg-dark-800 border border-dark-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
                >
                  <option value="african">Africains / Afrique (défaut)</option>
                  <option value="caucasian">Blancs / caucasiens</option>
                  <option value="global">Mixte international</option>
                </select>
                <p className="text-xs text-dark-500 mt-1">Par défaut AutoEdit génère des scènes africaines modernes. Tu peux changer pour une autre audience.</p>
              </div>
            )}
            <ToggleRow
              icon={<Music className="w-4 h-4 text-primary-400" />}
              label="Musique"
              checked={!!options.music}
              onChange={toggle('music')}
            />
            <ToggleRow
              icon={<Sparkles className="w-4 h-4 text-primary-400" />}
              label="Effets sonores (SFX)"
              checked={!!options.sfx}
              onChange={toggle('sfx')}
            />
            <ToggleRow
              icon={<Smartphone className="w-4 h-4 text-primary-400" />}
              label="Format vertical 9:16"
              checked={!!options.vertical_9_16}
              onChange={toggle('vertical_9_16')}
            />
            <ToggleRow
              icon={<Megaphone className="w-4 h-4 text-primary-400" />}
              label="CTA final"
              checked={!!options.final_cta}
              onChange={toggle('final_cta')}
            />
          </div>

          {/* Branding */}
          <div className="card space-y-3">
            <h3 className="font-semibold">Branding (optionnel)</h3>
            <div>
              <label className="text-xs text-dark-400 block mb-1">Texte intro / logo</label>
              <input
                type="text"
                maxLength={60}
                value={logoText}
                onChange={(e) => setLogoText(e.target.value)}
                placeholder="Ex. Lance ton e-commerce"
                className="w-full bg-dark-800 border border-dark-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 block mb-1">Texte du CTA final</label>
              <input
                type="text"
                maxLength={120}
                value={ctaText}
                onChange={(e) => setCtaText(e.target.value)}
                placeholder="Ex. Abonne-toi 🔔"
                className="w-full bg-dark-800 border border-dark-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-primary-500"
              />
            </div>
          </div>

          {/* Pipeline steps preview */}
          <div className="card">
            <h3 className="font-semibold mb-3">Étapes du pipeline</h3>
            <div className="space-y-2 text-sm">
              <PipelineStep icon={<Mic className="w-4 h-4 text-primary-400" />} label="Transcription Whisper (mot-par-mot)" />
              <PipelineStep icon={<VolumeX className="w-4 h-4 text-primary-400" />} label="Détection silences & filler words" />
              <PipelineStep icon={<Film className="w-4 h-4 text-primary-400" />} label="EDL — plan de coupes" />
              {options.motion_design && (
                <PipelineStep icon={<PenTool className="w-4 h-4 text-primary-400" />} label="Motion design — scènes illustrées animées" />
              )}
              {options.ai_broll && (
                <PipelineStep icon={<ImageIcon className="w-4 h-4 text-primary-400" />} label="B-roll IA (images générées)" />
              )}
              <PipelineStep icon={<Sparkles className="w-4 h-4 text-primary-400" />} label="Captions, musique, export FFmpeg" />
            </div>
          </div>

          {/* AutoEdit Button */}
          <button
            onClick={handleAutoEdit}
            disabled={processing}
            className="btn-accent w-full py-4 text-lg flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {processing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Traitement…
              </>
            ) : (
              <>
                <Zap className="w-5 h-5" />
                Lancer AutoEdit
              </>
            )}
          </button>

          {!!completedResult?.transcription && (
            <div className="card">
              <h3 className="font-semibold mb-2">Transcription</h3>
              <p className="text-sm text-dark-400 max-h-40 overflow-y-auto leading-relaxed">
                {typeof (completedResult.transcription as { text?: unknown }).text === 'string'
                  ? (completedResult.transcription as { text: string }).text
                  : ''}
              </p>
            </div>
          )}

          {Array.isArray(completedResult?.steps_completed) && (
            <div className="card">
              <h3 className="font-semibold mb-2">Résumé</h3>
              <div className="text-sm space-y-1">
                {(completedResult!.steps_completed as string[]).map((step) => (
                  <div key={step} className="flex items-center gap-2 text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    {step.replace(/_/g, ' ')}
                  </div>
                ))}
                {Array.isArray(completedResult?.steps_failed) &&
                  (completedResult!.steps_failed as string[]).map((step) => (
                    <div key={step} className="flex items-center gap-2 text-red-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                      {step.replace(/_/g, ' ')} (échec)
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ToggleRow(props: {
  icon: React.ReactNode
  label: string
  checked: boolean
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <label className="flex items-center justify-between py-2 cursor-pointer">
      <span className="flex items-center gap-2 text-sm text-dark-200">
        {props.icon}
        {props.label}
      </span>
      <input
        type="checkbox"
        checked={props.checked}
        onChange={props.onChange}
        className="w-4 h-4 accent-primary-500"
      />
    </label>
  )
}

function PipelineStep(props: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 text-dark-300">
      {props.icon}
      {props.label}
    </div>
  )
}
