import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Film, Trash2, Clock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import UploadZone from '../components/video/UploadZone'
import { listVideos, deleteVideo } from '../api/videos'
import { useAuthStore } from '../store/authStore'
import { getMe } from '../api/auth'

interface Video {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
  created_at: string
}

const statusIcons: Record<string, typeof Film> = {
  uploaded: Clock,
  processing: Loader2,
  ready: CheckCircle,
  error: AlertCircle,
}

const statusColors: Record<string, string> = {
  uploaded: 'text-dark-400',
  processing: 'text-primary-400',
  ready: 'text-emerald-400',
  error: 'text-red-400',
}

export default function Dashboard() {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { setUser, user } = useAuthStore()

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [videosData, userData] = await Promise.all([
        listVideos(),
        getMe(),
      ])
      setVideos(videosData.videos)
      setUser(userData)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleUploadComplete = (video: { id: string; title: string }) => {
    navigate(`/editor/${video.id}`)
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteVideo(id)
      setVideos(videos.filter((v) => v.id !== id))
    } catch {
      // ignore
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-dark-400 mt-1">
            {user ? `${user.plan.toUpperCase()} plan` : 'Manage your videos'}
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
          <div className="grid gap-4">
            {videos.map((video) => {
              const StatusIcon = statusIcons[video.status] || Film
              const statusColor = statusColors[video.status] || 'text-dark-400'

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
                        {video.duration_s && ` · ${Math.round(video.duration_s)}s`}
                        {' · '}
                        {new Date(video.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <span className={`flex items-center gap-1 text-sm ${statusColor}`}>
                      <StatusIcon className={`w-4 h-4 ${video.status === 'processing' ? 'animate-spin' : ''}`} />
                      {video.status}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(video.id)
                      }}
                      className="text-dark-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
