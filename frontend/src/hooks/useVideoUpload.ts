import { useState, useCallback } from 'react'
import { uploadVideo } from '../api/videos'

export function useVideoUpload() {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const upload = useCallback(async (file: File) => {
    setUploading(true)
    setProgress(0)
    setError(null)

    try {
      const result = await uploadVideo(file, setProgress)
      return result
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
      throw err
    } finally {
      setUploading(false)
    }
  }, [])

  return { upload, uploading, progress, error }
}
