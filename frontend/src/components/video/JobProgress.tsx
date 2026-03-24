import { useEffect, useState } from 'react'
import { getJob } from '../../api/jobs'
import { Loader2, CheckCircle, XCircle, Download } from 'lucide-react'

interface Props {
  jobId: string
  onComplete?: (result: Record<string, unknown>) => void
}

export default function JobProgress({ jobId, onComplete }: Props) {
  const [job, setJob] = useState<{
    status: string
    progress: number
    result: Record<string, unknown> | null
    error_message: string | null
  } | null>(null)

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>

    const poll = async () => {
      try {
        const data = await getJob(jobId)
        setJob(data)

        if (data.status === 'completed') {
          clearInterval(interval)
          onComplete?.(data.result || {})
        } else if (data.status === 'failed') {
          clearInterval(interval)
        }
      } catch {
        // silently retry
      }
    }

    poll()
    interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [jobId, onComplete])

  if (!job) return null

  const statusConfig = {
    pending: { icon: Loader2, color: 'text-dark-400', label: 'Waiting...' },
    processing: { icon: Loader2, color: 'text-primary-400', label: 'Processing...' },
    completed: { icon: CheckCircle, color: 'text-emerald-400', label: 'Complete!' },
    failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
  }

  const config = statusConfig[job.status as keyof typeof statusConfig] || statusConfig.pending
  const Icon = config.icon

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-4">
        <Icon className={`w-6 h-6 ${config.color} ${job.status === 'processing' || job.status === 'pending' ? 'animate-spin' : ''}`} />
        <div>
          <p className={`font-medium ${config.color}`}>{config.label}</p>
          {job.status === 'processing' && (
            <p className="text-sm text-dark-400">{job.progress}% complete</p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {(job.status === 'processing' || job.status === 'pending') && (
        <div className="w-full bg-dark-700 rounded-full h-2 mb-3">
          <div
            className="bg-primary-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${job.progress}%` }}
          />
        </div>
      )}

      {job.status === 'failed' && job.error_message && (
        <p className="text-sm text-red-400 bg-red-400/10 rounded-lg p-3">{job.error_message}</p>
      )}

      {job.status === 'completed' && (
        <a
          href={`/api/v1/jobs/${jobId}/download`}
          className="btn-accent inline-flex items-center gap-2"
          download
        >
          <Download className="w-4 h-4" />
          Download Video
        </a>
      )}
    </div>
  )
}
