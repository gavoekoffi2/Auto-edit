import { useCallback, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { Upload, Film } from 'lucide-react'
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
      className={`group relative cursor-pointer overflow-hidden rounded-3xl p-10 text-center sm:p-14 ${
        uploading ? 'pointer-events-none' : ''
      }`}
      style={{
        // Bordure pointillée dessinée en SVG plutôt qu'en `border-dashed`: le
        // tiret natif se déforme sur les grands rayons et « craque » dans les
        // angles. Ici il reste régulier tout autour, à toutes les tailles.
        backgroundColor: isDragActive ? 'rgba(63,114,255,0.07)' : 'rgba(255,255,255,0.018)',
        backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='none' rx='24' ry='24' stroke='%23${
          isDragActive ? '6593ff' : 'ffffff2e'
        }' stroke-width='2' stroke-dasharray='10%2c 12' stroke-linecap='round'/%3e%3c/svg%3e")`,
        transform: isDragActive ? 'scale(1.006)' : 'none',
        transition: 'all 0.35s var(--ease-premium)',
      }}
    >
      <input {...getInputProps()} />

      {/* halo d'ambiance */}
      <div
        className={`pointer-events-none absolute left-1/2 top-0 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-600/25 blur-[90px] transition-opacity duration-500 ${
          isDragActive || uploading ? 'opacity-100' : 'opacity-0 group-hover:opacity-70'
        }`}
        aria-hidden
      />

      {uploading ? (
        <div className="relative flex flex-col items-center gap-5">
          {/* Anneau de progression: le chiffre au centre est l'information,
              l'anneau en est la lecture périphérique. */}
          <div className="relative grid h-20 w-20 place-items-center">
            <div className="ring-progress absolute inset-0 rounded-full" style={{ '--p': progress } as React.CSSProperties} />
            <span className="font-display text-lg font-bold tabular-nums">{progress}%</span>
          </div>
          <p className="text-heading font-semibold">Envoi de ta vidéo…</p>
          <div className="bar-track h-1.5 w-full max-w-md">
            <div className="bar-fill" data-live="true" style={{ width: `${Math.max(progress, 3)}%` }} />
          </div>
          <p className="max-w-sm text-sm leading-relaxed text-dark-400">
            {uploadHelperText(progress)}
            {selectedFileSize ? ` Taille: ${formatFileSize(selectedFileSize)}.` : ''}
          </p>
        </div>
      ) : (
        <div className="relative flex flex-col items-center gap-5">
          <div
            className="grid h-16 w-16 place-items-center rounded-2xl border border-white/[0.09] bg-gradient-to-br from-primary-600/30 via-iris-600/20 to-transparent shadow-e2"
            style={{
              transform: isDragActive ? 'scale(1.12) rotate(-4deg)' : 'none',
              transition: 'transform 0.4s var(--ease-snap)',
            }}
          >
            {isDragActive
              ? <Film className="h-7 w-7 text-primary-200" />
              : <Upload className="h-7 w-7 text-primary-200 transition-transform duration-500 ease-premium group-hover:-translate-y-1" />}
          </div>
          <div>
            <p className="text-heading font-semibold">
              {isDragActive ? 'Lâche ta vidéo ici' : 'Glisse ta vidéo parlée ici'}
            </p>
            <p className="mt-2 text-sm text-dark-400">
              ou clique pour parcourir — {ALLOWED_VIDEO_EXTENSIONS.slice(0, 4).map((ext) => ext.toUpperCase()).join(', ')}…
              · max {MAX_FILE_SIZE_MB / 1024} Go
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            {['Coupes', 'Collage papier', 'Sous-titres', 'Sound design'].map((step) => (
              <span
                key={step}
                className="rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1 text-[11px] font-medium text-dark-400"
              >
                {step}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
