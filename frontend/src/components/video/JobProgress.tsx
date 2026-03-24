import { useEffect, useState, useCallback } from 'react'
import { getJob, downloadJobResult } from '../../api/jobs'
import { Loader2, CheckCircle, XCircle, Download, RefreshCw } from 'lucide-react'
import { toast } from '../ui/Toast'

interface Props {
  jobId: string
  onComplete?: (result: Record<string, unknown>) => void
  onRetry?: () => void
}

export default function JobProgress({ jobId, onComplete, onRetry }: Props) {
  const [job, setJob] = useState<{
    status: string
    progress: number
    result: Record<string, unknown> | null
    error_message: string | null
  } | null>(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    let cancelled = false

    const poll = async () => {
      try {
        const data = await getJob(jobId)
        if (cancelled) return
        setJob(data)

        if (data.status === 'completed') {
          clearInterval(interval)
          onComplete?.(data.result || {})
          toast('success', 'Video processing complete!')
        } else if (data.status === 'failed') {
          clearInterval(interval)
          toast('error', data.error_message || 'Processing failed')
        }
      } catch {
        // silently retry on polling errors
      }
    }

    poll()
    interval = setInterval(poll, 2000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [jobId, onComplete])

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
  }

  const config = statusConfig[job.status as keyof typeof statusConfig] || statusConfig.pending
  const Icon = config.icon
  const isAnimating = job.status === 'processing' || job.status === 'pending'

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

      {/* Progress bar */}
      {isAnimating && (
        <div className="w-full bg-dark-700 rounded-full h-2 mb-3">
          <div
            className="bg-primary-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${job.progress}%` }}
          />
        </div>
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
