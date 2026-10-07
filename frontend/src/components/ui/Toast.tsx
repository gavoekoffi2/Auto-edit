import { useEffect, useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'info'
  message: string
}

let addToastFn: ((type: ToastMessage['type'], message: string) => void) | null = null

export function toast(type: ToastMessage['type'], message: string) {
  if (addToastFn) addToastFn(type, message)
}

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
}

const tints = {
  success: 'text-emerald-300 bg-emerald-400/12 ring-emerald-400/25',
  error: 'text-red-300 bg-red-400/12 ring-red-400/25',
  info: 'text-primary-300 bg-primary-500/12 ring-primary-500/25',
}

/** Une erreur mérite qu'on ait le temps de la lire; un succès, non. */
const LIFETIME = { success: 4000, info: 5000, error: 8000 }

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback((type: ToastMessage['type'], message: string) => {
    const id = Math.random().toString(36).slice(2)
    // Au-delà de trois, la pile masque l'interface qu'elle commente. Les plus
    // anciennes sortent d'elles-mêmes.
    setToasts((prev) => [...prev.slice(-2), { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, LIFETIME[type])
  }, [])

  useEffect(() => {
    addToastFn = addToast
    return () => {
      addToastFn = null
    }
  }, [addToast])

  const dismiss = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id))

  return (
    // `aria-live="polite"`: annoncé aux lecteurs d'écran sans interrompre la
    // tâche en cours. La pile s'ancre EN HAUT — en bas, elle passerait sous la
    // barre d'onglets mobile.
    <div
      className="pointer-events-none fixed inset-x-4 top-20 z-[70] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-5 sm:items-end"
      role="status"
      aria-live="polite"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const Icon = icons[t.type]
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: -14, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, scale: 0.96 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="glass-panel pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl px-4 py-3"
            >
              <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg ring-1 ${tints[t.type]}`}>
                <Icon className="h-3.5 w-3.5" />
              </span>
              <p className="flex-1 text-sm leading-relaxed text-dark-100">{t.message}</p>
              <button
                onClick={() => dismiss(t.id)}
                className="-mr-1 mt-0.5 rounded-md p-1 text-dark-500 transition-colors hover:bg-white/5 hover:text-white"
                aria-label="Fermer la notification"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
