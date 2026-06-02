import { useEffect, useState, useCallback } from 'react'
import { getJob } from '../api/jobs'

interface Job {
  id: string
  status: string
  progress: number
  result: Record<string, unknown> | null
  error_message: string | null
}

export function useJobPolling(jobId: string | null, intervalMs = 2000) {
  const [job, setJob] = useState<Job | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  const poll = useCallback(async () => {
    if (!jobId) return
    try {
      const data = await getJob(jobId)
      setJob(data)
      return data
    } catch {
      return null
    }
  }, [jobId])

  useEffect(() => {
    if (!jobId) return

    setIsPolling(true)
    let interval: ReturnType<typeof setInterval>

    const startPolling = async () => {
      const data = await poll()
      if (data?.status === 'completed' || data?.status === 'failed') {
        setIsPolling(false)
        return
      }

      interval = setInterval(async () => {
        const result = await poll()
        if (result?.status === 'completed' || result?.status === 'failed') {
          clearInterval(interval)
          setIsPolling(false)
        }
      }, intervalMs)
    }

    startPolling()
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [jobId, intervalMs, poll])

  return { job, isPolling }
}
