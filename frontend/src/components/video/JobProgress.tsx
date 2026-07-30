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
  const [connectionWarning, setConnectionWarning] = useState('')

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined
    let cancelled = false
    // `settled` est indispensable: le PREMIER poll part avant que `interval`
    // n'existe. Si le job est déjà terminé à ce moment-là, `clearInterval`
    // recevait `undefined`, l'intervalle démarrait ensuite quand même et
    // rejouait `onComplete` + le toast « terminé » toutes les 2 secondes.
    let settled = false
    let errorCount = 0
    let warnedAboutConnection = false

    const stop = () => {
      settled = true
      if (interval !== undefined) clearInterval(interval)
    }

    const poll = async () => {
      if (settled) return
      try {
        const data = await getJob(jobId)
        if (cancelled || settled) return
        errorCount = 0
        warnedAboutConnection = false
        setConnectionWarning('')
        setJob(data)

        if (data.status === 'completed') {
          stop()
          onComplete?.(data.result || {})
          toast('success', 'Montage terminé !')
        } else if (data.status === 'failed') {
          stop()
          toast('error', data.error_message || 'Le traitement a échoué')
        } else if (data.status === 'cancelled') {
          stop()
          onCancelled?.()
          toast('info', 'Traitement annulé')
        }
      } catch {
        errorCount++
        if (errorCount >= 5 && !cancelled) {
          setConnectionWarning(
            "Connexion instable. Ne ferme pas la page : le traitement continue sur le serveur et CutForge va reprendre le suivi automatiquement.",
          )
          if (!warnedAboutConnection) {
            warnedAboutConnection = true
            toast('info', 'Connexion instable, mais le traitement continue sur le serveur.')
          }
        }
      }
    }

    poll()
    if (!settled) interval = setInterval(poll, 2000)
    const resumePolling = () => {
      if (!cancelled && !settled) poll()
    }
    window.addEventListener('focus', resumePolling)
    document.addEventListener('visibilitychange', resumePolling)
    return () => {
      cancelled = true
      stop()
      window.removeEventListener('focus', resumePolling)
      document.removeEventListener('visibilitychange', resumePolling)
    }
  }, [jobId, onComplete, onCancelled])

  const handleDownload = useCallback(async () => {
    setDownloading(true)
    try {
      await downloadJobResult(jobId)
      toast('success', 'Téléchargement lancé')
    } catch {
      toast('error', 'Le téléchargement a échoué. Réessaie.')
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
    pending: { icon: Loader2, color: 'text-dark-400', label: 'En file d’attente…' },
    processing: { icon: Loader2, color: 'text-primary-400', label: 'Montage en cours…' },
    completed: { icon: CheckCircle, color: 'text-emerald-400', label: 'Montage terminé' },
    failed: { icon: XCircle, color: 'text-red-400', label: 'Échec' },
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
            <p className="text-sm text-dark-400">{job.progress} % effectués</p>
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

      {connectionWarning && isAnimating && (
        <p className="text-xs text-amber-300 bg-amber-400/10 rounded-lg p-3 mb-3">
          {connectionWarning}
        </p>
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
            {job.error_message || 'Une erreur inattendue est survenue'}
          </p>
          {onRetry && (
            <button onClick={onRetry} className="btn-secondary text-sm flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />
              Relancer le montage
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
          {downloading ? 'Téléchargement…' : 'Télécharger la vidéo'}
        </button>
      )}
    </div>
  )
}
