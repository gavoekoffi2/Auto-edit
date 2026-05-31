import { useEffect, useState, useCallback, useRef } from 'react'
import { getJob, downloadJobResult, cancelJob } from '../../api/jobs'
import { Loader2, CheckCircle, XCircle, Download, RefreshCw, Ban, Volume2, Type, Sparkles, Mic, Film } from 'lucide-react'
import { toast } from '../ui/Toast'

interface Props {
  jobId: string
  onComplete?: (result: Record<string, unknown>) => void
  onRetry?: () => void
}

const PIPELINE_STEPS = [
  { key: 'transcription', label: 'AI Transcription', icon: Mic },
  { key: 'silence_removal', label: 'Silence Removal', icon: Volume2 },
  { key: 'scene_detection', label: 'Scene Detection', icon: Film },
  { key: 'effects', label: 'Effects & Subtitles', icon: Sparkles },
  { key: 'sound_effects', label: 'Sound Effects', icon: Volume2 },
  { key: 'subtitle_styling', label: 'Subtitle Styling', icon: Type },
]

export default function JobProgress({ jobId, onComplete, onRetry }: Props) {
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete
  const [job, setJob] = useState<{
    status: string
    progress: number
    result: Record<string, unknown> | null
    error_message: string | null
    params?: Record<string, unknown>
  } | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    let cancelled = false
    let errorCount = 0

    const poll = async () => {
      try {
        const data = await getJob(jobId)
        if (cancelled) return
        errorCount = 0
        setJob(data)

        if (data.status === 'completed') {
          clearInterval(interval)
          onCompleteRef.current?.(data.result || {})
          toast('success', 'Video processing complete!')
        } else if (data.status === 'failed') {
          clearInterval(interval)
          toast('error', data.error_message || 'Processing failed')
        } else if (data.status === 'cancelled') {
          clearInterval(interval)
        }
      } catch {
        errorCount++
        if (errorCount >= 5 && !cancelled) {
          clearInterval(interval)
          toast('error', 'Lost connection to server. Please refresh the page.')
        }
      }
    }

    poll()
    interval = setInterval(poll, 2000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [jobId])

  const handleCancel = useCallback(async () => {
    setCancelling(true)
    try {
      await cancelJob(jobId)
      setJob((prev) => (prev ? { ...prev, status: 'cancelled' } : prev))
      toast('info', 'Job cancelled')
    } catch {
      toast('error', 'Could not cancel job')
    } finally {
      setCancelling(false)
    }
  }, [jobId])

  const handleDownload = useCallback(async () => {
    setDownloading(true)
    try {
      await downloadJobResult(jobId)
      toast('success', 'Download started!')
    } catch {
      toast('error', 'Download failed. Please try again.')
    } finally {
      setDownloading(false)
    }
  }, [jobId])

  if (!job) return null

  const statusConfig = {
    pending: { icon: Loader2, color: 'text-dark-400', label: 'Waiting in queue...' },
    processing: { icon: Loader2, color: 'text-primary-400', label: 'Processing...' },
    completed: { icon: CheckCircle, color: 'text-emerald-400', label: 'Complete!' },
    failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
    cancelled: { icon: Ban, color: 'text-dark-400', label: 'Cancelled' },
  }

  const config = statusConfig[job.status as keyof typeof statusConfig] || statusConfig.pending
  const Icon = config.icon
  const isAnimating = job.status === 'processing' || job.status === 'pending'

  // Determine which steps are active based on job params
  const sfxEnabled = (job.params?.sfx as { enabled?: boolean })?.enabled !== false
  const subtitleStyle = job.params?.subtitle_style as { preset?: string } | undefined
  const activeSteps = PIPELINE_STEPS.filter((step) => {
    if (step.key === 'sound_effects') return sfxEnabled
    if (step.key === 'subtitle_styling') return !!subtitleStyle
    return true
  })

  // Estimate which step is currently running based on progress
  const currentStepIndex = Math.min(
    Math.floor((job.progress / 100) * activeSteps.length),
    activeSteps.length - 1
  )

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-4">
        <Icon className={`w-6 h-6 ${config.color} ${isAnimating ? 'animate-spin' : ''}`} />
        <div>
          <p className={`font-medium ${config.color}`}>{config.label}</p>
          {job.status === 'processing' && (
            <p className="text-sm text-dark-400">{job.progress}% complete</p>
          )}
        </div>
      </div>

      {/* Processing steps breakdown */}
      {isAnimating && (
        <div className="space-y-1.5 mb-4">
          {activeSteps.map((step, i) => {
            const StepIcon = step.icon
            const isDone = i < currentStepIndex
            const isCurrent = i === currentStepIndex && job.status === 'processing'
            return (
              <div
                key={step.key}
                className={`flex items-center gap-2 text-xs ${
                  isDone
                    ? 'text-emerald-400'
                    : isCurrent
                    ? 'text-primary-400'
                    : 'text-dark-500'
                }`}
              >
                {isDone ? (
                  <CheckCircle className="w-3.5 h-3.5" />
                ) : isCurrent ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <StepIcon className="w-3.5 h-3.5" />
                )}
                <span>{step.label}</span>
                {step.key === 'subtitle_styling' && subtitleStyle?.preset && (
                  <span className="text-dark-500">({subtitleStyle.preset})</span>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Progress bar */}
      {isAnimating && (
        <>
          <div className="w-full bg-dark-700 rounded-full h-2 mb-3">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${job.progress}%` }}
            />
          </div>
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="text-sm text-dark-400 hover:text-red-400 transition-colors inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            {cancelling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Ban className="w-3.5 h-3.5" />}
            {cancelling ? 'Cancelling...' : 'Cancel'}
          </button>
        </>
      )}

      {job.status === 'failed' && (
        <div className="space-y-3">
          <p className="text-sm text-red-400 bg-red-400/10 rounded-lg p-3">
            {job.error_message || 'An unknown error occurred'}
          </p>
          {onRetry && (
            <button onClick={onRetry} className="btn-secondary text-sm flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          )}
        </div>
      )}

      {job.status === 'completed' && (
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="btn-accent inline-flex items-center gap-2"
        >
          {downloading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          {downloading ? 'Downloading...' : 'Download Video'}
        </button>
      )}
    </div>
  )
}
