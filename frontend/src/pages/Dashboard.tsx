import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Film, Trash2, Clock, CheckCircle, AlertCircle, Loader2, ChevronLeft, ChevronRight, Download } from 'lucide-react'
import UploadZone from '../components/video/UploadZone'
import { listVideos, deleteVideo } from '../api/videos'
import { listJobs, downloadJobResult } from '../api/jobs'
import { useAuthStore } from '../store/authStore'
import { getMe } from '../api/auth'
import { toast } from '../components/ui/Toast'

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
  ready: CheckCircle,
  completed: CheckCircle,
  failed: AlertCircle,
  error: AlertCircle,
}

const statusColors: Record<string, string> = {
  uploaded: 'text-dark-400',
  processing: 'text-primary-400',
  pending: 'text-primary-400',
  ready: 'text-emerald-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  error: 'text-red-400',
}

function getDisplayStatus(video: Video, latestJob?: JobSummary) {
  if (latestJob?.status === 'completed') return 'Montage terminé'
  if (latestJob?.status === 'processing') return `Montage ${latestJob.progress ?? 0}%`
  if (latestJob?.status === 'pending') return 'Montage en attente'
  if (latestJob?.status === 'failed') return 'Montage échoué'
  if (video.status === 'ready') return 'Vidéo prête'
  if (video.status === 'uploaded') return 'Importée'
  if (video.status === 'processing') return 'Traitement...'
  if (video.status === 'error') return 'Erreur'
  return video.status
}

function getStatusKey(video: Video, latestJob?: JobSummary) {
  return latestJob?.status || video.status
}

const PAGE_SIZE = 10

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
      toast('error', 'Failed to load dashboard data')
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
    if (!confirm('Delete this video? This cannot be undone.')) return

    // Optimistic update
    setVideos((prev) => prev.filter((v) => v.id !== id))
    try {
      await deleteVideo(id)
      toast('success', 'Video deleted')
      setTotal((t) => t - 1)
    } catch {
      toast('error', 'Failed to delete video')
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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-dark-400 mt-1">
            {user ? `${(user.effective_plan || user.plan).toUpperCase()} plan` : 'Manage your videos'}
            {total > 0 && ` · ${total} video${total !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      {/* Upload Zone */}
      <div className="mb-8">
        <UploadZone onUploadComplete={handleUploadComplete} />
      </div>

      {/* Video List */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Your Videos</h2>

        {loading ? (
          <div className="text-center py-12">
            <Loader2 className="w-8 h-8 text-primary-500 animate-spin mx-auto" />
          </div>
        ) : videos.length === 0 ? (
          <div className="card text-center py-12">
            <Film className="w-12 h-12 text-dark-600 mx-auto mb-4" />
            <p className="text-dark-400">No videos yet. Upload your first video above!</p>
          </div>
        ) : (
          <>
            <div className="grid gap-4">
              {videos.map((video) => {
                const latestJob = latestJobs[video.id]
                const statusKey = getStatusKey(video, latestJob)
                const StatusIcon = statusIcons[statusKey] || Film
                const statusColor = statusColors[statusKey] || 'text-dark-400'
                const hasCompletedMontage = Boolean(latestJob?.status === 'completed' && latestJob.result?.output_path)

                return (
                  <div
                    key={video.id}
                    className="card flex items-center justify-between hover:border-dark-600 transition-colors cursor-pointer"
                    onClick={() => navigate(`/editor/${video.id}`)}
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-dark-800 rounded-lg flex items-center justify-center">
                        <Film className="w-6 h-6 text-dark-500" />
                      </div>
                      <div>
                        <h3 className="font-medium">{video.title}</h3>
                        <p className="text-sm text-dark-500">
                          {formatSize(video.size_bytes)}
                          {video.duration_s != null && ` · ${formatDuration(video.duration_s)}`}
                          {' · '}
                          {new Date(video.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className={`flex items-center gap-1 text-sm ${statusColor}`}>
                        <StatusIcon className={`w-4 h-4 ${statusKey === 'processing' || statusKey === 'pending' ? 'animate-spin' : ''}`} />
                        {getDisplayStatus(video, latestJob)}
                      </span>
                      {hasCompletedMontage && latestJob && (
                        <button
                          onClick={(e) => handleDownload(latestJob.id, e)}
                          className="btn-secondary py-2 px-3 text-xs flex items-center gap-1"
                          aria-label="Download final montage"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Montage
                        </button>
                      )}
                      <button
                        onClick={(e) => handleDelete(video.id, e)}
                        className="text-dark-500 hover:text-red-400 transition-colors"
                        aria-label="Delete video"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="btn-secondary py-2 px-3 disabled:opacity-30"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-dark-400">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="btn-secondary py-2 px-3 disabled:opacity-30"
                  aria-label="Next page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
