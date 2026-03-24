import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Zap, Mic, VolumeX, Film, Sparkles, Loader2 } from 'lucide-react'
import VideoPlayer from '../components/video/VideoPlayer'
import Timeline from '../components/video/Timeline'
import JobProgress from '../components/video/JobProgress'
import { getVideo, getStreamUrl } from '../api/videos'
import { createJob, listJobs } from '../api/jobs'

type EditMode = 'tiktok' | 'youtube' | 'podcast'

interface Video {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
}

export default function Editor() {
  const { videoId } = useParams<{ videoId: string }>()
  const [video, setVideo] = useState<Video | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [selectedMode, setSelectedMode] = useState<EditMode>('youtube')
  const [processing, setProcessing] = useState(false)
  const [completedResult, setCompletedResult] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    if (!videoId) return
    loadVideo()
    loadJobs()
  }, [videoId])

  const loadVideo = async () => {
    try {
      const data = await getVideo(videoId!)
      setVideo(data)
    } catch {
      // ignore
    }
  }

  const loadJobs = async () => {
    try {
      const jobs = await listJobs(videoId!)
      const activeJob = jobs.find((j: { status: string }) => j.status === 'processing' || j.status === 'pending')
      if (activeJob) {
        setActiveJobId(activeJob.id)
        setProcessing(true)
      }
      const completed = jobs.find((j: { status: string }) => j.status === 'completed')
      if (completed) {
        setCompletedResult(completed.result)
      }
    } catch {
      // ignore
    }
  }

  const handleAutoEdit = async () => {
    if (!videoId) return
    setProcessing(true)

    try {
      const job = await createJob({
        video_id: videoId,
        job_type: 'pipeline',
        mode: selectedMode,
      })
      setActiveJobId(job.id)
    } catch (err: unknown) {
      setProcessing(false)
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Failed to start processing'
      alert(msg)
    }
  }

  const handleJobComplete = (result: Record<string, unknown>) => {
    setCompletedResult(result)
    setProcessing(false)
    loadVideo()
  }

  const modes = [
    { id: 'tiktok' as const, name: 'TikTok', icon: '🔥', desc: 'Vertical, fast, subtitled' },
    { id: 'youtube' as const, name: 'YouTube', icon: '🎥', desc: 'Optimized engagement' },
    { id: 'podcast' as const, name: 'Podcast', icon: '🎙️', desc: 'Audio cleanup' },
  ]

  if (!video) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    )
  }

  const scenes = completedResult?.scenes as { scenes: { start: number; end: number; duration: number }[] } | undefined

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{video.title}</h1>
        <p className="text-dark-400 text-sm">
          {video.status} · {(video.size_bytes / (1024 * 1024)).toFixed(1)} MB
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Video Preview */}
        <div className="lg:col-span-2 space-y-4">
          <VideoPlayer src={getStreamUrl(videoId!)} />

          {/* Timeline */}
          {scenes?.scenes && (
            <Timeline
              scenes={scenes.scenes}
              totalDuration={video.duration_s || 0}
            />
          )}

          {/* Job Progress */}
          {activeJobId && processing && (
            <JobProgress jobId={activeJobId} onComplete={handleJobComplete} />
          )}
        </div>

        {/* Controls Sidebar */}
        <div className="space-y-4">
          {/* Mode Selection */}
          <div className="card">
            <h3 className="font-semibold mb-3">Editing Mode</h3>
            <div className="space-y-2">
              {modes.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all text-left
                    ${selectedMode === mode.id
                      ? 'border-primary-500 bg-primary-500/10'
                      : 'border-dark-700 hover:border-dark-500'
                    }`}
                >
                  <span className="text-2xl">{mode.icon}</span>
                  <div>
                    <p className="font-medium">{mode.name}</p>
                    <p className="text-xs text-dark-400">{mode.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Pipeline Steps */}
          <div className="card">
            <h3 className="font-semibold mb-3">Processing Steps</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-dark-300">
                <Mic className="w-4 h-4 text-primary-400" />
                AI Transcription (Whisper)
              </div>
              <div className="flex items-center gap-2 text-dark-300">
                <VolumeX className="w-4 h-4 text-primary-400" />
                Silence Removal (auto-editor)
              </div>
              <div className="flex items-center gap-2 text-dark-300">
                <Film className="w-4 h-4 text-primary-400" />
                Scene Detection (PySceneDetect)
              </div>
              <div className="flex items-center gap-2 text-dark-300">
                <Sparkles className="w-4 h-4 text-primary-400" />
                Effects & Subtitles (MoviePy)
              </div>
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
                Processing...
              </>
            ) : (
              <>
                <Zap className="w-5 h-5" />
                AutoEdit Now
              </>
            )}
          </button>

          {/* Transcription result */}
          {completedResult?.transcription && (
            <div className="card">
              <h3 className="font-semibold mb-2">Transcription</h3>
              <p className="text-sm text-dark-400 max-h-40 overflow-y-auto">
                {(completedResult.transcription as { text: string }).text}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
