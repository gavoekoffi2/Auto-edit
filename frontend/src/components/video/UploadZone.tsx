import { useCallback, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { Upload, Film, Loader2 } from 'lucide-react'
import axios from 'axios'
import {
  ALLOWED_VIDEO_EXTENSIONS,
  MAX_FILE_SIZE_MB,
  uploadVideo,
  validateVideoFile,
} from '../../api/videos'
import { toast } from '../ui/Toast'

interface Props {
  onUploadComplete: (video: { id: string; title: string }) => void
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function uploadHelperText(progress: number) {
  if (progress >= 100) return 'Finalisation côté serveur… ne ferme pas la page.'
  if (progress >= 1) return 'Upload en cours. Sur mobile, une grosse vidéo peut prendre plusieurs minutes.'
  return 'Préparation sécurisée de la session…'
}

export default function UploadZone({ onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [selectedFileSize, setSelectedFileSize] = useState<number | null>(null)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    try {
      validateVideoFile(file)
      setUploading(true)
      setProgress(0)
      setSelectedFileSize(file.size)
      const video = await uploadVideo(file, setProgress)
      toast('success', 'Vidéo envoyée avec succès !')
      onUploadComplete(video)
    } catch (err: unknown) {
      let msg = 'Upload échoué. Vérifie ta connexion puis réessaie.'
      if (axios.isAxiosError(err)) {
        msg = err.response?.data?.detail || err.message || msg
        if (err.code === 'ECONNABORTED' || msg.toLowerCase().includes('timeout')) {
          msg = "La connexion a été trop lente. J'ai corrigé le timeout: recharge la page puis réessaie."
        } else if (!err.response) {
          msg = 'Connexion interrompue pendant l’upload. Garde la page ouverte et réessaie avec un Wi‑Fi/4G stable.'
        }
      } else if (err instanceof Error) {
        msg = err.message
      }
      toast('error', msg)
    } finally {
      setUploading(false)
      setProgress(0)
      setSelectedFileSize(null)
    }
  }, [onUploadComplete])

  const onDropRejected = useCallback((rejections: FileRejection[]) => {
    const rejection = rejections[0]
    const fileName = rejection?.file?.name ? ` “${rejection.file.name}”` : ''
    const codes = rejection?.errors?.map((err) => err.code) ?? []

    if (codes.includes('file-too-large')) {
      toast('error', `Vidéo${fileName} trop lourde. Maximum: ${MAX_FILE_SIZE_MB}MB.`)
      return
    }

    if (codes.includes('file-invalid-type')) {
      toast('error', `Format${fileName} non supporté. Utilise: ${ALLOWED_VIDEO_EXTENSIONS.map((ext) => ext.toUpperCase()).join(', ')}.`)
      return
    }

    toast('error', rejection?.errors?.[0]?.message || 'Impossible de sélectionner cette vidéo.')
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      'video/*': ALLOWED_VIDEO_EXTENSIONS.map((ext) => `.${ext}`),
    },
    maxFiles: 1,
    maxSize: MAX_FILE_SIZE_MB * 1024 * 1024,
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
          <p className="text-lg font-medium">Upload... {progress}%</p>
          <div className="w-full max-w-xs bg-dark-700 rounded-full h-2">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-sm text-dark-400 max-w-sm">
            {uploadHelperText(progress)}
            {selectedFileSize ? ` Taille: ${formatFileSize(selectedFileSize)}.` : ''}
          </p>
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
            <p className="text-dark-500 mt-1">
              or click to browse ({ALLOWED_VIDEO_EXTENSIONS.map((ext) => ext.toUpperCase()).join(', ')} - max {MAX_FILE_SIZE_MB}MB)
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
