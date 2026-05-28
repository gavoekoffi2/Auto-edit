import { useEffect, useState, useCallback } from 'react'
import { getJob } from '../api/jobs'

interface Job {
  id: string
  status: string
  progress: number
  result: Record<string, unknown> | null
  error_message: string | null
}

const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled']

export function useJobPolling(jobId: string | null, intervalMs = 2000) {
  const [job, setJob] = useState<Job | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  const poll = useCallback(async () => {
    if (!jobId) return null
    try {
      return await getJob(jobId)
    } catch {
      return null
    }
  }, [jobId])

  useEffect(() => {
    if (!jobId) return

    let interval: ReturnType<typeof setInterval> | undefined
    let stopped = false

    const stop = () => {
      stopped = true
      if (interval) clearInterval(interval)
      setIsPolling(false)
    }

    setIsPolling(true)

    const tick = async () => {
      const data = await poll()
      if (stopped) return
      if (data) {
        setJob(data)
        if (TERMINAL_STATUSES.includes(data.status)) {
          stop()
        }
      }
    }

    // Kick off immediately, then on an interval. The interval is assigned
    // synchronously so unmount cleanup always clears it (no async race).
    interval = setInterval(tick, intervalMs)
    void tick()

    return stop
  }, [jobId, intervalMs, poll])

  return { job, isPolling }
}
