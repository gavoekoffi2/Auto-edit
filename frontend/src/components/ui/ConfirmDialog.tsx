import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'

interface Props {
  open: boolean
  title: string
  message: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'neutral'
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Demande de confirmation.
 *
 * Remplace `window.confirm()`. Ce n'est pas une question d'esthétique: la boîte
 * native impose le style du système d'exploitation au milieu du produit, elle
 * **bloque le fil d'exécution** du navigateur, et sur mobile elle affiche le
 * nom de domaine en gros au-dessus du message — l'utilisateur a l'impression
 * que le site tente quelque chose plutôt que de lui poser une question.
 *
 * Cette version-ci retient le focus, se ferme à Échap, rend l'action
 * destructrice visuellement distincte, et rend la main pendant l'appel réseau
 * (`busy`) au lieu de figer l'écran.
 */
export default function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirmer', cancelLabel = 'Annuler',
  tone = 'danger', busy = false, onConfirm, onCancel,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)
  const restoreTo = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    restoreTo.current = document.activeElement as HTMLElement
    document.body.style.overflow = 'hidden'
    // Le focus part sur ANNULER, pas sur l'action destructrice: une frappe
    // « Entrée » réflexe ne doit jamais supprimer une vidéo.
    requestAnimationFrame(() => confirmRef.current?.focus())

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel()
        return
      }
      if (event.key !== 'Tab' || !panelRef.current) return
      const focusable = panelRef.current.querySelectorAll<HTMLElement>('button')
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', onKey)
      restoreTo.current?.focus()
    }
  }, [open, onCancel])

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-[60] flex items-end justify-center p-4 sm:items-center"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onCancel}
            aria-hidden
          />
          <motion.div
            ref={panelRef}
            initial={{ opacity: 0, y: 18, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            className="glass-panel relative w-full max-w-md rounded-2xl p-6"
          >
            <div className="flex items-start gap-3.5">
              <span
                className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ring-1 ${
                  tone === 'danger'
                    ? 'bg-red-500/12 text-red-300 ring-red-500/25'
                    : 'bg-primary-500/12 text-primary-300 ring-primary-500/25'
                }`}
              >
                <AlertTriangle className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <h2 id="confirm-title" className="text-heading font-semibold">{title}</h2>
                <div className="mt-1.5 text-sm leading-relaxed text-dark-400">{message}</div>
              </div>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                ref={confirmRef}
                onClick={onCancel}
                disabled={busy}
                className="btn-secondary !px-5 !py-2.5 text-sm"
              >
                {cancelLabel}
              </button>
              <button
                onClick={onConfirm}
                disabled={busy}
                className={`!px-5 !py-2.5 text-sm ${tone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
              >
                {busy ? 'Un instant…' : confirmLabel}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
