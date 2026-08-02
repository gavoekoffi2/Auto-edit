import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertCircle, CheckCircle, ChevronLeft, ChevronRight, Clapperboard, Clock,
  Download, Film, Loader2, Play, Plus, Sparkles, Trash2,
} from 'lucide-react'
import UploadZone from '../components/video/UploadZone'
import Metric from '../components/ui/Metric'
import Surface from '../components/ui/Surface'
import { listVideos, deleteVideo } from '../api/videos'
import { listJobs, downloadJobResult } from '../api/jobs'
import { useAuthStore } from '../store/authStore'
import { getMe } from '../api/auth'
import { toast } from '../components/ui/Toast'
import { BRAND } from '../brand'

interface Video {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
  created_at: string
}

interface JobSummary {
  id: string
  status: string
  progress: number
  result?: Record<string, unknown> | null
}

const statusIcons: Record<string, typeof Film> = {
  uploaded: Clock,
  processing: Loader2,
  pending: Loader2,
  ready: CheckCircle,
  completed: CheckCircle,
  failed: AlertCircle,
  error: AlertCircle,
}

const statusTones: Record<string, 'ok' | 'busy' | 'error' | 'neutral'> = {
  uploaded: 'neutral',
  processing: 'busy',
  pending: 'busy',
  ready: 'ok',
  completed: 'ok',
  failed: 'error',
  error: 'error',
}

function getDisplayStatus(video: Video, latestJob?: JobSummary) {
  if (latestJob?.status === 'completed') return 'Montage terminé'
  if (latestJob?.status === 'processing') return `Montage ${latestJob.progress ?? 0}%`
  if (latestJob?.status === 'pending') return 'Montage en attente'
  if (latestJob?.status === 'failed') return 'Montage échoué'
  if (video.status === 'ready') return 'Vidéo prête'
  if (video.status === 'uploaded') return 'Importée'
  if (video.status === 'processing') return 'Traitement…'
  if (video.status === 'error') return 'Erreur'
  return video.status
}

function getStatusKey(video: Video, latestJob?: JobSummary) {
  return latestJob?.status || video.status
}

const PAGE_SIZE = 10

/** Vignettes: quatre ambiances de forge, assignées par position (stable). */
const THUMB_GRADIENTS = [
  'from-[#16203f] via-[#243161] to-[#0c1024]',
  'from-[#2a1631] via-[#43204f] to-[#150b1a]',
  'from-[#0f2b27] via-[#14433b] to-[#081a16]',
  'from-[#332008] via-[#4d3113] to-[#1a1007]',
]

export default function Dashboard() {
  const [videos, setVideos] = useState<Video[]>([])
  const [latestJobs, setLatestJobs] = useState<Record<string, JobSummary | undefined>>({})
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { setUser, user } = useAuthStore()

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [videosData, userData] = await Promise.all([
        listVideos(page * PAGE_SIZE, PAGE_SIZE),
        user ? Promise.resolve(null) : getMe(),
      ])
      setVideos(videosData.videos)
      setTotal(videosData.total)
      const jobEntries = await Promise.all(
        videosData.videos.map(async (video: Video) => {
          try {
            const jobs = await listJobs(video.id) as JobSummary[]
            return [video.id, jobs[0]] as const
          } catch {
            return [video.id, undefined] as const
          }
        }),
      )
      setLatestJobs(Object.fromEntries(jobEntries))
      if (userData) setUser(userData)
    } catch {
      toast('error', 'Impossible de charger le studio')
    } finally {
      setLoading(false)
    }
  }, [page, user, setUser])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleUploadComplete = (video: { id: string; title: string }) => {
    navigate(`/editor/${video.id}`)
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Supprimer cette vidéo ? Cette action est définitive.')) return

    // Optimistic update
    setVideos((prev) => prev.filter((v) => v.id !== id))
    try {
      await deleteVideo(id)
      toast('success', 'Vidéo supprimée')
      setTotal((t) => t - 1)
    } catch {
      toast('error', 'Suppression impossible')
      loadData() // Reload on error
    }
  }

  const handleDownload = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await downloadJobResult(jobId)
    } catch {
      toast('error', 'Impossible de télécharger le montage')
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const firstName = user?.email?.split('@')[0] || 'créateur'
  const doneCount = Object.values(latestJobs).filter((j) => j?.status === 'completed').length
  const busyCount = Object.values(latestJobs).filter(
    (j) => j?.status === 'processing' || j?.status === 'pending',
  ).length

  return (
    <div className="mx-auto max-w-[1400px] py-8 shell-gutter sm:py-10">
      {/* ======================= EN-TÊTE ======================= */}
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="eyebrow">Studio {BRAND.name}</p>
          <h1 className="mt-2.5 text-title font-bold">
            Salut <span className="gradient-text">{firstName}</span>
          </h1>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-dark-400">
            Dépose une vidéo parlée&nbsp;: {BRAND.name} coupe, illustre, sous-titre
            et sonorise. Tu récupères un montage prêt à publier.
          </p>
        </div>

        <a href="#upload" className="btn-accent inline-flex w-fit items-center gap-2 text-sm">
          <Plus className="h-4 w-4" />
          Nouveau montage
        </a>
      </div>

      {/* ======================= INDICATEURS ======================= */}
      <div className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Metric icon={Film} label="Vidéos importées" value={total} tint="primary" />
        <Metric
          icon={Clapperboard}
          label="Montages terminés"
          value={doneCount}
          tint="emerald"
          hint="sur cette page"
        />
        <Metric icon={Sparkles} label="En cours de forge" value={busyCount} tint="amber" />
      </div>

      {/* ======================= IMPORT ======================= */}
      <div id="upload" className="mt-7 scroll-mt-24">
        <UploadZone onUploadComplete={handleUploadComplete} />
      </div>

      {/* ======================= BIBLIOTHÈQUE ======================= */}
      <div className="mt-12">
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h2 className="text-heading font-semibold">Tes vidéos</h2>
          {total > 0 && (
            <span className="text-xs text-dark-500">
              {total} vidéo{total !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid gap-3">
            {[0, 1, 2].map((i) => (
              <Surface key={i} className="flex items-center gap-5 !p-4">
                <div className="skeleton h-[72px] w-32 shrink-0" />
                <div className="flex-1 space-y-2.5">
                  <div className="skeleton h-4 w-1/3" />
                  <div className="skeleton h-3 w-1/4" />
                </div>
                <div className="skeleton h-7 w-28 rounded-full" />
              </Surface>
            ))}
          </div>
        ) : videos.length === 0 ? (
          <EmptyLibrary />
        ) : (
          <>
            <div className="grid gap-3">
              {videos.map((video, idx) => (
                <VideoRow
                  key={video.id}
                  video={video}
                  index={idx}
                  latestJob={latestJobs[video.id]}
                  onOpen={() => navigate(`/editor/${video.id}`)}
                  onDelete={(e) => handleDelete(video.id, e)}
                  onDownload={handleDownload}
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-4">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="btn-secondary !px-3 !py-2 disabled:opacity-30"
                  aria-label="Page précédente"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-xs text-dark-500">
                  Page {page + 1} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="btn-secondary !px-3 !py-2 disabled:opacity-30"
                  aria-label="Page suivante"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Une vidéo de la bibliothèque                                                */
/* -------------------------------------------------------------------------- */
function VideoRow(props: {
  video: Video
  index: number
  latestJob?: JobSummary
  onOpen: () => void
  onDelete: (e: React.MouseEvent) => void
  onDownload: (jobId: string, e: React.MouseEvent) => void
}) {
  const { video, index, latestJob } = props
  const statusKey = getStatusKey(video, latestJob)
  const StatusIcon = statusIcons[statusKey] || Film
  const tone = statusTones[statusKey] || 'neutral'
  const isBusy = statusKey === 'processing' || statusKey === 'pending'
  const done = Boolean(latestJob?.status === 'completed' && latestJob.result?.output_path)
  const grad = THUMB_GRADIENTS[index % THUMB_GRADIENTS.length]
  const progress = latestJob?.progress ?? 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      // Le décalage se plafonne à 5: au-delà, la dernière carte d'une longue
      // liste arriverait une seconde après la première, ce qui se voit comme
      // une lenteur, pas comme une intention.
      transition={{ duration: 0.4, delay: Math.min(index, 5) * 0.045, ease: [0.22, 1, 0.36, 1] }}
    >
      <Surface
        interactive
        flush
        role="button"
        tabIndex={0}
        onClick={props.onOpen}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            props.onOpen()
          }
        }}
        className="group flex cursor-pointer flex-col gap-4 p-3.5 sm:flex-row sm:items-center"
      >
        {/* vignette */}
        <div className={`relative h-[72px] w-full shrink-0 overflow-hidden rounded-xl bg-gradient-to-br sm:w-[124px] ${grad}`}>
          <span className="absolute inset-0 grid place-items-center">
            <span className="grid h-9 w-9 place-items-center rounded-full border border-white/15 bg-black/25 backdrop-blur-sm transition-transform duration-500 ease-premium group-hover:scale-110">
              <Play className="ml-0.5 h-3.5 w-3.5 fill-white/80 text-white/80" />
            </span>
          </span>
          {video.duration_s != null && (
            <span className="absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums">
              {formatDuration(video.duration_s)}
            </span>
          )}
          {done && (
            <span className="absolute left-1.5 top-1.5 rounded bg-emerald-500/90 px-1.5 py-0.5 text-[9px] font-bold tracking-wider">
              MONTÉ
            </span>
          )}
        </div>

        {/* infos */}
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-medium leading-tight">{video.title}</h3>
          <p className="mt-1 text-xs text-dark-500">
            {formatSize(video.size_bytes)}
            {' · '}
            {new Date(video.created_at).toLocaleDateString('fr-FR', {
              day: 'numeric', month: 'short', year: 'numeric',
            })}
          </p>
          {isBusy && (
            <div className="mt-2.5 flex items-center gap-2.5">
              <div className="bar-track h-1.5 w-full max-w-[220px]">
                <div className="bar-fill" data-live="true" style={{ width: `${Math.max(progress, 4)}%` }} />
              </div>
              <span className="text-[11px] font-semibold tabular-nums text-primary-300">{progress}%</span>
            </div>
          )}
        </div>

        {/* statut + actions */}
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <span className="status-pill" data-tone={tone}>
            <StatusIcon className={`h-3.5 w-3.5 ${isBusy ? 'animate-spin' : ''}`} />
            {getDisplayStatus(video, latestJob)}
          </span>
          {done && latestJob && (
            <button
              onClick={(e) => props.onDownload(latestJob.id, e)}
              className="btn-accent flex items-center gap-1.5 !px-3 !py-2 text-xs"
              aria-label="Télécharger le montage final"
            >
              <Download className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Montage</span>
            </button>
          )}
          <button
            onClick={props.onDelete}
            className="rounded-lg p-2 text-dark-600 transition-colors hover:bg-red-400/10 hover:text-red-400"
            aria-label="Supprimer la vidéo"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </Surface>
    </motion.div>
  )
}

/* -------------------------------------------------------------------------- */
function EmptyLibrary() {
  return (
    <Surface className="relative overflow-hidden py-16 text-center">
      <div className="halo left-1/2 top-[-40%] h-[300px] w-[300px] -translate-x-1/2 bg-primary-600/30" aria-hidden />
      <div className="relative">
        <div className="mx-auto mb-5 grid h-[72px] w-[72px] place-items-center rounded-3xl border border-white/[0.08] bg-white/[0.04]">
          <Clapperboard className="h-8 w-8 text-primary-300" />
        </div>
        <h3 className="text-heading font-semibold">Ta bibliothèque est vide</h3>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-dark-400">
          Envoie ta première vidéo parlée ci-dessus — {BRAND.name} s'occupe des
          coupes, du collage papier, des sons et des sous-titres.
        </p>
        <a href="#upload" className="btn-primary mt-6 inline-flex items-center gap-2 text-sm">
          <Plus className="h-4 w-4" /> Envoyer une vidéo
        </a>
      </div>
    </Surface>
  )
}

/* -------------------------------------------------------------------------- */
function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(sec: number) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
