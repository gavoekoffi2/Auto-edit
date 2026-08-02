import { useEffect, useState, useCallback } from 'react'
import ConfirmDialog from '../ui/ConfirmDialog'
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
  const [askCancel, setAskCancel] = useState(false)
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
    setAskCancel(false)
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
  const stage = currentStage(job.progress)

  return (
    <div className="panel">
      <div className="flex items-center gap-4">
        {/* L'anneau porte le pourcentage: pendant un rendu de plusieurs
            minutes, c'est la seule chose que l'utilisateur regarde. */}
        <div className="relative grid h-14 w-14 shrink-0 place-items-center">
          <div
            className="ring-progress absolute inset-0 rounded-full"
            style={{ '--p': isAnimating ? Math.max(job.progress, 3) : 100 } as React.CSSProperties}
          />
          {isAnimating ? (
            <span className="font-display text-xs font-bold tabular-nums">{job.progress}%</span>
          ) : (
            <Icon className={`h-5 w-5 ${config.color}`} />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p className={`text-sm font-semibold ${config.color}`}>{config.label}</p>
          <p className="mt-1 truncate text-xs text-dark-500">
            {isAnimating ? stage : 'Le rendu est disponible ci-dessous.'}
          </p>
          {isAnimating && (
            <div className="bar-track mt-2.5 h-1.5">
              <div
                className="bar-fill"
                data-live="true"
                style={{ width: `${Math.max(job.progress, 3)}%` }}
              />
            </div>
          )}
        </div>
      </div>

      {connectionWarning && isAnimating && (
        <p className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/[0.08] p-3 text-xs leading-relaxed text-amber-300">
          {connectionWarning}
        </p>
      )}

      {isAnimating && (
        <button
          onClick={() => setAskCancel(true)}
          disabled={cancelling}
          className="btn-secondary mt-4 inline-flex items-center gap-2 !px-4 !py-2 text-xs"
        >
          {cancelling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Ban className="h-4 w-4" />}
          {cancelling ? 'Annulation…' : 'Annuler le traitement'}
        </button>
      )}

      {job.status === 'failed' && (
        <div className="mt-4 space-y-3">
          <p className="rounded-xl border border-red-400/20 bg-red-400/[0.08] p-3 text-sm leading-relaxed text-red-300">
            {job.error_message || 'Une erreur inattendue est survenue'}
          </p>
          {onRetry && (
            <button onClick={onRetry} className="btn-secondary inline-flex items-center gap-2 !px-4 !py-2 text-xs">
              <RefreshCw className="h-4 w-4" />
              Relancer le montage
            </button>
          )}
        </div>
      )}

      <ConfirmDialog
        open={askCancel}
        busy={cancelling}
        title="Annuler ce montage ?"
        message="Le rendu en cours sera interrompu. Tu pourras le relancer, mais la progression déjà faite sera perdue."
        confirmLabel="Annuler le montage"
        cancelLabel="Laisser tourner"
        onConfirm={handleCancel}
        onCancel={() => setAskCancel(false)}
      />

      {job.status === 'completed' && (
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="btn-accent mt-4 inline-flex items-center gap-2 text-sm"
        >
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {downloading ? 'Téléchargement…' : 'Télécharger la vidéo'}
        </button>
      )}
    </div>
  )
}

/**
 * Étape lisible déduite de l'avancement.
 *
 * Le backend renvoie un pourcentage, pas un libellé. Un pourcentage seul
 * pendant quatre minutes donne l'impression d'un blocage; nommer ce qui se
 * passe transforme l'attente en démonstration de ce que le produit fait.
 * Les bornes suivent l'ordre réel des étapes du moteur.
 */
function currentStage(progress: number): string {
  if (progress < 12) return 'Préparation de la vidéo…'
  if (progress < 30) return 'Transcription de la parole…'
  if (progress < 45) return 'Découpe des silences et des hésitations…'
  if (progress < 62) return 'Choix des illustrations et du collage…'
  if (progress < 78) return 'Motion design et sous-titres animés…'
  if (progress < 92) return 'Sound design et mixage…'
  return 'Encodage final…'
}
