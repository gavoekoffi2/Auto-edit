import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, Film, Loader2 } from 'lucide-react'
import { uploadVideo } from '../../api/videos'

interface Props {
  onUploadComplete: (video: { id: string; title: string }) => void
}

export default function UploadZone({ onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploading(true)
    setError('')
    setProgress(0)

    try {
      const video = await uploadVideo(file, setProgress)
      onUploadComplete(video)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
    } finally {
      setUploading(false)
    }
  }, [onUploadComplete])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    },
    maxFiles: 1,
    disabled: uploading,
  })

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-200
        ${isDragActive ? 'border-primary-500 bg-primary-500/10' : 'border-dark-600 hover:border-dark-400 hover:bg-dark-900/50'}
        ${uploading ? 'pointer-events-none opacity-70' : ''}`}
    >
      <input {...getInputProps()} />

      {uploading ? (
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 text-primary-500 animate-spin" />
          <p className="text-lg font-medium">Uploading... {progress}%</p>
          <div className="w-64 bg-dark-700 rounded-full h-2">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          {isDragActive ? (
            <Film className="w-12 h-12 text-primary-500" />
          ) : (
            <Upload className="w-12 h-12 text-dark-500" />
          )}
          <div>
            <p className="text-lg font-medium">
              {isDragActive ? 'Drop your video here' : 'Drag & drop your video'}
            </p>
            <p className="text-dark-500 mt-1">or click to browse (MP4, MOV, AVI, MKV, WebM)</p>
          </div>
        </div>
      )}

      {error && <p className="text-red-400 mt-4">{error}</p>}
    </div>
  )
}
