import { useState, useCallback } from 'react'
import { uploadVideo, waitForVideoCompressed } from '../api/videos'

export type UploadPhase = 'idle' | 'uploading' | 'compressing' | 'done' | 'error'

export function useVideoUpload() {
  const [phase, setPhase] = useState<UploadPhase>('idle')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  // Keep backwards-compatible boolean for components that only need to know
  // whether any async work is in progress.
  const uploading = phase === 'uploading' || phase === 'compressing'

  const upload = useCallback(async (file: File) => {
    setPhase('uploading')
    setProgress(0)
    setError(null)

    try {
      const result = await uploadVideo(file, setProgress)

      // If the server started background compression, wait for it.
      if (result.status === 'compressing') {
        setPhase('compressing')
        const ready = await waitForVideoCompressed(result.id, undefined, 5 * 60 * 1000)
        setPhase('done')
        return ready
      }

      setPhase('done')
      return result
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
      setPhase('error')
      throw err
    }
  }, [])

  const reset = useCallback(() => {
    setPhase('idle')
    setProgress(0)
    setError(null)
  }, [])

  return { upload, uploading, phase, progress, error, reset }
}
