import { useCallback, useState } from ‘react’
import { useDropzone, type FileRejection } from ‘react-dropzone’
import { Upload, Film, Loader2, Zap } from ‘lucide-react’
import axios from ‘axios’
import {
  ALLOWED_VIDEO_EXTENSIONS,
  MAX_FILE_SIZE_MB,
  validateVideoFile,
  waitForVideoCompressed,
} from ‘../../api/videos’
import { uploadVideo } from ‘../../api/videos’
import { toast } from ‘../ui/Toast’

interface Props {
  onUploadComplete: (video: { id: string; title: string }) => void
}

type UploadPhase = ‘uploading’ | ‘compressing’

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function uploadHelperText(progress: number) {
  if (progress >= 100) return ‘Finalisation côté serveur… ne ferme pas la page.’
  if (progress >= 1) return ‘Upload en cours. Sur mobile, une grosse vidéo peut prendre plusieurs minutes.’
  return ‘Préparation sécurisée de la session…’
}

export default function UploadZone({ onUploadComplete }: Props) {
  const [phase, setPhase] = useState<UploadPhase | null>(null)
  const [progress, setProgress] = useState(0)
  const [selectedFileSize, setSelectedFileSize] = useState<number | null>(null)

  const uploading = phase !== null

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    try {
      validateVideoFile(file)
      setPhase(‘uploading’)
      setProgress(0)
      setSelectedFileSize(file.size)

      const video = await uploadVideo(file, setProgress)

      // If the server launched background compression, poll until done.
      if (video.status === ‘compressing’) {
        setPhase(‘compressing’)
        const ready = await waitForVideoCompressed(video.id, undefined, 5 * 60 * 1000)
        toast(‘success’, ‘Vidéo optimisée et prête !’)
        onUploadComplete(ready as { id: string; title: string })
      } else {
        toast(‘success’, ‘Vidéo envoyée avec succès !’)
        onUploadComplete(video)
      }
    } catch (err: unknown) {
      let msg = ‘Upload échoué. Vérifie ta connexion puis réessaie.’
      if (axios.isAxiosError(err)) {
        msg = err.response?.data?.detail || err.message || msg
        if (err.code === ‘ECONNABORTED’ || msg.toLowerCase().includes(‘timeout’)) {
          msg = “La connexion a été trop lente. J’ai corrigé le timeout: recharge la page puis réessaie.”
        } else if (!err.response) {
          msg = ‘Connexion interrompue pendant l’upload. Garde la page ouverte et réessaie avec un Wi‑Fi/4G stable.’
        }
      } else if (err instanceof Error) {
        msg = err.message
      }
      toast(‘error’, msg)
    } finally {
      setPhase(null)
      setProgress(0)
      setSelectedFileSize(null)
    }
  }, [onUploadComplete])

  const onDropRejected = useCallback((rejections: FileRejection[]) => {
    const rejection = rejections[0]
    const fileName = rejection?.file?.name ? ` “${rejection.file.name}”` : ‘’
    const codes = rejection?.errors?.map((err) => err.code) ?? []

    if (codes.includes(‘file-too-large’)) {
      toast(‘error’, `Vidéo${fileName} trop lourde. Maximum: ${MAX_FILE_SIZE_MB}MB.`)
      return
    }

    if (codes.includes(‘file-invalid-type’)) {
      toast(‘error’, `Format${fileName} non supporté. Utilise: ${ALLOWED_VIDEO_EXTENSIONS.map((ext) => ext.toUpperCase()).join(‘, ‘)}.`)
      return
    }

    toast(‘error’, rejection?.errors?.[0]?.message || ‘Impossible de sélectionner cette vidéo.’)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      ‘video/*’: ALLOWED_VIDEO_EXTENSIONS.map((ext) => `.${ext}`),
    },
    maxFiles: 1,
    maxSize: MAX_FILE_SIZE_MB * 1024 * 1024,
    disabled: uploading,
  })

  return (
    <div
      {...getRootProps()}
      className={`group relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-10 text-center sm:p-14
        ${isDragActive
          ? ‘border-primary-400 bg-primary-500/10 scale-[1.01]’
          : ‘border-dark-600 bg-dark-900/40 hover:border-primary-500/60 hover:bg-dark-900/70’}
        ${uploading ? ‘pointer-events-none border-primary-500/40’ : ‘’}`}
      style={{ transition: ‘all 0.3s var(--ease-out-expo)’ }}
    >
      <input {...getInputProps()} />

      {/* halo d’ambiance */}
      <div
        className={`pointer-events-none absolute left-1/2 top-0 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-600/25 blur-3xl transition-opacity duration-500 ${
          isDragActive || uploading ? ‘opacity-100’ : ‘opacity-0 group-hover:opacity-70’
        }`}
        aria-hidden
      />

      {phase === ‘compressing’ ? (
        <div className=”relative flex flex-col items-center gap-4”>
          <div className=”relative”>
            <Zap className=”h-12 w-12 animate-pulse text-fuchsia-400” />
          </div>
          <p className=”text-lg font-semibold”>Optimisation de la vidéo…</p>
          <div className=”h-2 w-full max-w-md overflow-hidden rounded-full bg-dark-700”>
            <div className=”h-full animate-pulse rounded-full bg-gradient-to-r from-fuchsia-500 via-primary-400 to-accent-400” />
          </div>
          <p className=”max-w-sm text-sm text-dark-400”>
            Compression intelligente en cours — réduit la taille jusqu’à 70% sans perte de qualité. Ne ferme pas la page.
          </p>
        </div>
      ) : phase === ‘uploading’ ? (
        <div className=”relative flex flex-col items-center gap-4”>
          <div className=”relative”>
            <Loader2 className=”h-12 w-12 animate-spin text-primary-400” />
            <span className=”absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white”>
              {progress}%
            </span>
          </div>
          <p className=”text-lg font-semibold”>Envoi de ta vidéo…</p>
          <div className=”h-2 w-full max-w-md overflow-hidden rounded-full bg-dark-700”>
            <div
              className=”h-full rounded-full bg-gradient-to-r from-primary-500 via-fuchsia-400 to-accent-400 transition-all duration-300”
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className=”max-w-sm text-sm text-dark-400”>
            {uploadHelperText(progress)}
            {selectedFileSize ? ` Taille: ${formatFileSize(selectedFileSize)}.` : ‘’}
          </p>
        </div>
      ) : (
        <div className=”relative flex flex-col items-center gap-5”>
          <div
            className={`flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-tr from-primary-600/30 to-fuchsia-500/20 ${
              isDragActive ? ‘scale-110’ : ‘group-hover:-translate-y-1’
            }`}
            style={{ transition: ‘transform 0.3s var(--ease-out-expo)’ }}
          >
            {isDragActive ? (
              <Film className=”h-7 w-7 text-primary-300” />
            ) : (
              <Upload className=”h-7 w-7 text-primary-300” />
            )}
          </div>
          <div>
            <p className=”text-lg font-semibold”>
              {isDragActive ? ‘Lâche ta vidéo ici ✨’ : ‘Glisse ta vidéo parlée ici’}
            </p>
            <p className=”mt-1.5 text-sm text-dark-400”>
              ou clique pour parcourir — {ALLOWED_VIDEO_EXTENSIONS.slice(0, 4).map((ext) => ext.toUpperCase()).join(‘, ‘)}…
              · max {MAX_FILE_SIZE_MB / 1024} Go
            </p>
          </div>
          <span className=”rounded-full border border-white/10 bg-white/5 px-3.5 py-1 text-xs text-dark-300”>
            ✂️ Coupes · 🎨 Motion design · 📝 Sous-titres · 🔊 SFX — automatiques
          </span>
        </div>
      )}
    </div>
  )
}
