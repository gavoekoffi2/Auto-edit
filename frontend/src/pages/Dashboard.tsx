import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Film, Trash2, Clock, CheckCircle, AlertCircle, Loader2, ChevronLeft,
  ChevronRight, Download, Sparkles, Crown, Plus, Clapperboard,
} from 'lucide-react'
import UploadZone from '../components/video/UploadZone'
import Reveal from '../components/ui/Reveal'
import Logo from '../components/ui/Logo'
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

const THUMB_GRADIENTS = [
  'from-[#1d2440] via-[#2a3566] to-[#101326]',
  'from-[#2a1a30] via-[#41254d] to-[#160d1c]',
  'from-[#102b27] via-[#15433c] to-[#0a1a17]',
  'from-[#33210f] via-[#4d3215] to-[#1a1108]',
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
    } catch (err) {
      toast('error', 'Impossible de charger le dashboard')
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

  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDuration = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const plan = (user?.effective_plan || user?.plan || 'free').toLowerCase()
  const firstName = user?.email?.split('@')[0] || 'créateur'
  const doneCount = Object.values(latestJobs).filter((j) => j?.status === 'completed').length
  const busyCount = Object.values(latestJobs).filter((j) => j?.status === 'processing' || j?.status === 'pending').length

  return (
    <div className="relative isolate overflow-x-clip">
      {/* fond d'ambiance */}
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] overflow-hidden" aria-hidden>
        <div className="cf-aurora left-[-8%] top-[-30%] h-[380px] w-[380px] bg-primary-600/40" />
        <div className="cf-aurora right-[-6%] top-[-20%] h-[320px] w-[320px] bg-fuchsia-600/25" style={{ animationDelay: '-7s' }} />
        <div className="cf-grid-dots absolute inset-0 opacity-70" />
      </div>

      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* ================= EN-TÊTE ================= */}
        <Reveal>
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="flex items-center gap-2 text-sm text-dark-400">
                <Logo size={18} /> {BRAND.name} Studio
              </p>
              <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
                Salut <span className="gradient-text">{firstName}</span> 👋
              </h1>
              <p className="mt-2 text-dark-400">
                Prêt à forger un nouveau montage&nbsp;?
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-bold tracking-wider ${
                  plan === 'free'
                    ? 'border border-white/10 bg-white/5 text-dark-300'
                    : 'border border-amber-300/40 bg-amber-300/10 text-amber-300'
                }`}
              >
                {plan !== 'free' && <Crown className="h-3.5 w-3.5" />}
                PLAN {plan.toUpperCase()}
              </span>
              <a href="#upload" className="btn-accent flex items-center gap-2 text-sm">
                <Plus className="h-4 w-4" />
                Nouveau montage
              </a>
            </div>
          </div>
        </Reveal>

        {/* ================= STATS ================= */}
        <Reveal delay={90}>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              { icon: Film, label: 'Vidéos importées', value: String(total), tint: 'text-primary-400 bg-primary-600/15' },
              { icon: Clapperboard, label: 'Montages terminés (page)', value: String(doneCount), tint: 'text-emerald-300 bg-emerald-400/10' },
              { icon: Sparkles, label: 'En cours de forge', value: String(busyCount), tint: 'text-amber-300 bg-amber-400/10' },
            ].map(({ icon: Icon, label, value, tint }) => (
              <div key={label} className="cf-card card flex items-center gap-4 !p-5">
                <span className={`flex h-11 w-11 items-center justify-center rounded-xl ${tint}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <div>
                  <p className="font-display text-2xl font-bold leading-none">{value}</p>
                  <p className="mt-1 text-xs text-dark-400">{label}</p>
                </div>
              </div>
            ))}
          </div>
        </Reveal>

        {/* ================= UPLOAD ================= */}
        <Reveal delay={160}>
          <div id="upload" className="mt-8 scroll-mt-24">
            <UploadZone onUploadComplete={handleUploadComplete} />
          </div>
        </Reveal>

        {/* ================= VIDÉOS ================= */}
        <div className="mt-12">
          <Reveal>
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Tes vidéos</h2>
              {total > 0 && (
                <span className="text-sm text-dark-400">{total} vidéo{total !== 1 ? 's' : ''}</span>
              )}
            </div>
          </Reveal>

          {loading ? (
            <div className="grid gap-4">
              {[0, 1, 2].map((i) => (
                <div key={i} className="card flex items-center gap-5 !p-4">
                  <div className="skeleton h-20 w-32 shrink-0" />
                  <div className="flex-1 space-y-2.5">
                    <div className="skeleton h-4 w-1/3" />
                    <div className="skeleton h-3 w-1/4" />
                  </div>
                  <div className="skeleton h-7 w-28 rounded-full" />
                </div>
              ))}
            </div>
          ) : videos.length === 0 ? (
            <Reveal>
              <div className="card relative overflow-hidden py-16 text-center">
                <div className="cf-aurora left-1/2 top-[-60%] h-[260px] w-[260px] -translate-x-1/2 bg-primary-600/30" aria-hidden />
                <div className="relative">
                  <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-white/5">
                    <Clapperboard className="h-9 w-9 text-primary-400" />
                  </div>
                  <h3 className="text-lg font-semibold">Aucune vidéo pour l'instant</h3>
                  <p className="mx-auto mt-2 max-w-sm text-sm text-dark-400">
                    Envoie ta première vidéo parlée ci-dessus — {BRAND.name} s'occupe des coupes,
                    du motion design, des sons et des sous-titres.
                  </p>
                  <a href="#upload" className="btn-primary mt-6 inline-flex items-center gap-2 text-sm">
                    <Plus className="h-4 w-4" /> Envoyer une vidéo
                  </a>
                </div>
              </div>
            </Reveal>
          ) : (
            <>
              <div className="grid gap-4">
                {videos.map((video, idx) => {
                  const latestJob = latestJobs[video.id]
                  const statusKey = getStatusKey(video, latestJob)
                  const StatusIcon = statusIcons[statusKey] || Film
                  const tone = statusTones[statusKey] || 'neutral'
                  const isBusy = statusKey === 'processing' || statusKey === 'pending'
                  const hasCompletedMontage = Boolean(latestJob?.status === 'completed' && latestJob.result?.output_path)
                  const grad = THUMB_GRADIENTS[idx % THUMB_GRADIENTS.length]

                  return (
                    <Reveal key={video.id} delay={Math.min(idx, 5) * 60}>
                      <div
                        className="cf-card card group flex cursor-pointer flex-col gap-4 !p-4 sm:flex-row sm:items-center"
                        onClick={() => navigate(`/editor/${video.id}`)}
                        onMouseMove={(e) => {
                          const r = e.currentTarget.getBoundingClientRect()
                          e.currentTarget.style.setProperty('--gx', `${e.clientX - r.left}px`)
                          e.currentTarget.style.setProperty('--gy', `${e.clientY - r.top}px`)
                        }}
                      >
                        {/* vignette */}
                        <div className={`relative h-20 w-full shrink-0 overflow-hidden rounded-xl bg-gradient-to-br sm:w-32 ${grad}`}>
                          <Film className="absolute left-1/2 top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 text-white/40 transition-transform duration-300 group-hover:scale-110" />
                          {video.duration_s != null && (
                            <span className="absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                              {formatDuration(video.duration_s)}
                            </span>
                          )}
                          {hasCompletedMontage && (
                            <span className="absolute left-1.5 top-1.5 rounded bg-emerald-500/90 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-white">
                              MONTÉ
                            </span>
                          )}
                        </div>

                        {/* infos */}
                        <div className="min-w-0 flex-1">
                          <h3 className="truncate font-medium">{video.title}</h3>
                          <p className="mt-1 text-sm text-dark-500">
                            {formatSize(video.size_bytes)}
                            {' · '}
                            {new Date(video.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })}
                          </p>
                          {isBusy && latestJob && (
                            <div className="mt-2 h-1 w-full max-w-[220px] overflow-hidden rounded-full bg-white/10">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-primary-500 to-cyan-400 transition-all duration-500"
                                style={{ width: `${latestJob.progress ?? 5}%` }}
                              />
                            </div>
                          )}
                        </div>

                        {/* statut + actions */}
                        <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                          <span className="status-pill" data-tone={tone}>
                            <StatusIcon className={`h-3.5 w-3.5 ${isBusy ? 'animate-spin' : ''}`} />
                            {getDisplayStatus(video, latestJob)}
                          </span>
                          {hasCompletedMontage && latestJob && (
                            <button
                              onClick={(e) => handleDownload(latestJob.id, e)}
                              className="btn-accent flex items-center gap-1.5 !px-3 !py-2 text-xs"
                              aria-label="Télécharger le montage final"
                            >
                              <Download className="h-3.5 w-3.5" />
                              Montage
                            </button>
                          )}
                          <button
                            onClick={(e) => handleDelete(video.id, e)}
                            className="rounded-lg p-2 text-dark-500 transition-colors hover:bg-red-400/10 hover:text-red-400"
                            aria-label="Supprimer la vidéo"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </Reveal>
                  )
                })}
              </div>

              {/* Pagination */}
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
                  <span className="text-sm text-dark-400">
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
    </div>
  )
}
