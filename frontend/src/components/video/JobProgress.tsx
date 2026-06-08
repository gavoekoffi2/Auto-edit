import { useEffect, useState, useCallback } from 'react'
import { getJob, downloadJobResult, cancelJob } from '../../api/jobs'
import { Loader2, CheckCircle, XCircle, Download, RefreshCw, Ban } from 'lucide-react'
import { toast } from '../ui/Toast'

interface Props {
  jobId: string
  onComplete?: (result: Record<string, unknown>) => void
  onRetry?: () => void
  onCancelled?: () => void
}

export default function JobProgress({ jobId, onComplete, onRetry, onCancelled }: Props) {
  const [job, setJob] = useState<{
    status: string
    progress: number
    result: Record<string, unknown> | null
    error_message: string | null
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
          onComplete?.(data.result || {})
          toast('success', 'Video processing complete!')
        } else if (data.status === 'failed') {
          clearInterval(interval)
          toast('error', data.error_message || 'Processing failed')
        } else if (data.status === 'cancelled') {
          clearInterval(interval)
          onCancelled?.()
          toast('info', 'Traitement annulé')
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
  }, [jobId, onComplete, onCancelled])

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

  const handleCancel = useCallback(async () => {
    if (!window.confirm('Annuler ce traitement vidéo ?')) return
    setCancelling(true)
    try {
      const data = await cancelJob(jobId)
      setJob(data)
      onCancelled?.()
      toast('info', 'Traitement annulé')
    } catch {
      toast('error', "Impossible d'annuler le traitement")
    } finally {
      setCancelling(false)
    }
  }, [jobId, onCancelled])

  if (!job) return null

  const statusConfig = {
    pending: { icon: Loader2, color: 'text-dark-400', label: 'Waiting in queue...' },
    processing: { icon: Loader2, color: 'text-primary-400', label: 'Processing...' },
    completed: { icon: CheckCircle, color: 'text-emerald-400', label: 'Complete!' },
    failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
    cancelled: { icon: Ban, color: 'text-amber-400', label: 'Annulé' },
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

      {isAnimating && (
        <button
          onClick={handleCancel}
          disabled={cancelling}
          className="btn-secondary text-sm inline-flex items-center gap-2 mb-3"
        >
          {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ban className="w-4 h-4" />}
          {cancelling ? 'Annulation...' : 'Annuler le traitement'}
        </button>
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
