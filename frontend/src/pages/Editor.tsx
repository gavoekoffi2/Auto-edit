import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Zap, Mic, VolumeX, Film, Sparkles, Loader2, ArrowLeft } from 'lucide-react'
import VideoPlayer from '../components/video/VideoPlayer'
import Timeline from '../components/video/Timeline'
import JobProgress from '../components/video/JobProgress'
import { getVideo, getStreamUrl } from '../api/videos'
import { createJob, listJobs } from '../api/jobs'
import { toast } from '../components/ui/Toast'

type EditMode = 'tiktok' | 'youtube' | 'podcast'

interface Video {
  id: string
  title: string
  duration_s: number | null
  size_bytes: number
  status: string
}

const MODES = [
  { id: 'tiktok' as const, name: 'TikTok', icon: '🔥', desc: 'Vertical, fast, subtitled' },
  { id: 'youtube' as const, name: 'YouTube', icon: '🎥', desc: 'Optimized engagement' },
  { id: 'podcast' as const, name: 'Podcast', icon: '🎙️', desc: 'Audio cleanup' },
] as const

export default function Editor() {
  const { videoId } = useParams<{ videoId: string }>()
  const navigate = useNavigate()
  const [video, setVideo] = useState<Video | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [selectedMode, setSelectedMode] = useState<EditMode>('youtube')
  const [processing, setProcessing] = useState(false)
  const [completedResult, setCompletedResult] = useState<Record<string, unknown> | null>(null)
  const [loadError, setLoadError] = useState('')

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

        // Check for active or completed jobs
        const activeJob = jobs.find((j: { status: string }) => j.status === 'processing' || j.status === 'pending')
        if (activeJob) {
          setActiveJobId(activeJob.id)
          setProcessing(true)
        }
        const completed = jobs.find((j: { status: string }) => j.status === 'completed')
        if (completed?.result) {
          setCompletedResult(completed.result)
        }
      } catch {
        if (!cancelled) setLoadError('Failed to load video')
      }
    }

    load()
    return () => { cancelled = true }
  }, [videoId])

  const handleAutoEdit = useCallback(async () => {
    if (!videoId) return
    setProcessing(true)

    try {
      const job = await createJob({
        video_id: videoId,
        job_type: 'pipeline',
        mode: selectedMode,
      })
      setActiveJobId(job.id)
      toast('info', `Processing started in ${selectedMode} mode`)
    } catch (err: unknown) {
      setProcessing(false)
      let msg = 'Failed to start processing'
      if (err && typeof err === 'object' && 'response' in err) {
        msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || msg
      }
      toast('error', msg)
    }
  }, [videoId, selectedMode])

  const handleJobComplete = useCallback((result: Record<string, unknown>) => {
    setCompletedResult(result)
    setProcessing(false)
    // Reload video data
    if (videoId) {
      getVideo(videoId).then(setVideo).catch(() => {})
    }
  }, [videoId])

  const handleRetry = useCallback(() => {
    setActiveJobId(null)
    setProcessing(false)
    handleAutoEdit()
  }, [handleAutoEdit])

  if (loadError) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center">
        <p className="text-red-400 mb-4">{loadError}</p>
        <button onClick={() => navigate('/dashboard')} className="btn-secondary">
          Back to Dashboard
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

  const scenes = completedResult?.scenes as { scenes: { start: number; end: number; duration: number }[] } | undefined

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-dark-400 hover:text-white transition-colors"
          aria-label="Back to dashboard"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">{video.title}</h1>
          <p className="text-dark-400 text-sm">
            {video.status}
            {' · '}
            {(video.size_bytes / (1024 * 1024)).toFixed(1)} MB
            {video.duration_s != null && ` · ${Math.floor(video.duration_s / 60)}:${Math.floor(video.duration_s % 60).toString().padStart(2, '0')}`}
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Video Preview */}
        <div className="lg:col-span-2 space-y-4">
          <VideoPlayer src={getStreamUrl(videoId!)} />

          {/* Timeline */}
          {scenes?.scenes && scenes.scenes.length > 0 && (
            <Timeline
              scenes={scenes.scenes}
              totalDuration={video.duration_s || 0}
            />
          )}

          {/* Job Progress */}
          {activeJobId && processing && (
            <JobProgress
              jobId={activeJobId}
              onComplete={handleJobComplete}
              onRetry={handleRetry}
            />
          )}
        </div>

        {/* Controls Sidebar */}
        <div className="space-y-4">
          {/* Mode Selection */}
          <div className="card">
            <h3 className="font-semibold mb-3">Editing Mode</h3>
            <div className="space-y-2">
              {MODES.map((mode) => (
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
              <p className="text-sm text-dark-400 max-h-40 overflow-y-auto leading-relaxed">
                {(completedResult.transcription as { text: string }).text}
              </p>
            </div>
          )}

          {/* Steps summary */}
          {completedResult?.steps_completed && (
            <div className="card">
              <h3 className="font-semibold mb-2">Processing Summary</h3>
              <div className="text-sm space-y-1">
                {(completedResult.steps_completed as string[]).map((step) => (
                  <div key={step} className="flex items-center gap-2 text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    {step.replace('_', ' ')}
                  </div>
                ))}
                {(completedResult.steps_failed as string[] | undefined)?.map((step) => (
                  <div key={step} className="flex items-center gap-2 text-red-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                    {step.replace('_', ' ')} (failed)
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
