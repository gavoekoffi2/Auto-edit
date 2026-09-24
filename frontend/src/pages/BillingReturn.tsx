import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle, Loader2, XCircle, Clock } from 'lucide-react'
import { verifyPayment, type PaymentStatus } from '../api/payments'
import { getMe } from '../api/auth'
import { getApiErrorMessage } from '../api/errors'
import { useAuthStore } from '../store/authStore'

const MAX_ATTEMPTS = 10
const RETRY_MS = 3000

/**
 * Page de retour FedaPay (`/billing/return?payment_id=…`).
 *
 * FedaPay y renvoie l'utilisateur après le paiement. On demande au backend de
 * relire la transaction chez FedaPay: l'abonnement est activé tout de suite,
 * même si le webhook est en retard. Tant que la transaction est « pending »
 * (validation Mobile Money sur le téléphone), on réessaie quelques fois.
 */
export default function BillingReturn() {
  const [params] = useSearchParams()
  const paymentId = params.get('payment_id') || ''
  const setUser = useAuthStore((s) => s.setUser)
  const [payment, setPayment] = useState<PaymentStatus | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!paymentId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const check = async (n: number) => {
      try {
        const data = await verifyPayment(paymentId)
        if (cancelled) return
        setPayment(data)
        setError('')
        if (data.status === 'completed') {
          getMe().then(setUser).catch(() => {})
          return
        }
        if (data.status === 'pending' && n + 1 < MAX_ATTEMPTS) {
          setAttempt(n + 1)
          timer = setTimeout(() => check(n + 1), RETRY_MS)
        }
      } catch (err) {
        if (cancelled) return
        setError(getApiErrorMessage(err, 'Vérification du paiement impossible.'))
        if (n + 1 < MAX_ATTEMPTS) {
          setAttempt(n + 1)
          timer = setTimeout(() => check(n + 1), RETRY_MS)
        }
      }
    }
    check(0)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [paymentId, setUser])

  const expires = payment?.subscription_expires_at
    ? new Date(payment.subscription_expires_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
    : null
  const stillChecking = !payment || (payment.status === 'pending' && attempt < MAX_ATTEMPTS - 1)

  let content: React.ReactNode
  if (!paymentId) {
    content = (
      <>
        <XCircle className="w-12 h-12 text-red-400 mx-auto" />
        <h1 className="text-2xl font-bold">Lien de paiement incomplet</h1>
        <p className="text-dark-400">Retourne sur la page des tarifs pour relancer le paiement.</p>
      </>
    )
  } else if (payment?.status === 'completed') {
    content = (
      <>
        <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto" />
        <h1 className="text-2xl font-bold">Paiement confirmé 🎉</h1>
        <p className="text-dark-300">
          Ton plan <strong className="uppercase">{payment.effective_plan}</strong> est actif
          {expires ? <> jusqu'au <strong>{expires}</strong></> : null}.
        </p>
      </>
    )
  } else if (payment?.status === 'failed') {
    content = (
      <>
        <XCircle className="w-12 h-12 text-red-400 mx-auto" />
        <h1 className="text-2xl font-bold">Paiement non abouti</h1>
        <p className="text-dark-400">
          Le paiement a été refusé ou annulé. Aucun montant n'a été débité pour cet abonnement.
        </p>
      </>
    )
  } else if (stillChecking && !error) {
    content = (
      <>
        <Loader2 className="w-12 h-12 text-primary-400 mx-auto animate-spin" />
        <h1 className="text-2xl font-bold">Confirmation du paiement…</h1>
        <p className="text-dark-400">
          Si tu paies par Mobile Money, valide la transaction sur ton téléphone. Ne ferme pas cette page.
        </p>
      </>
    )
  } else {
    content = (
      <>
        <Clock className="w-12 h-12 text-amber-300 mx-auto" />
        <h1 className="text-2xl font-bold">Paiement en attente</h1>
        <p className="text-dark-400">
          {error || "FedaPay n'a pas encore confirmé le paiement."} Ton plan sera activé automatiquement
          dès la confirmation. Si le montant a été débité et que rien ne change d'ici une heure, contacte le support
          en indiquant la référence <code className="text-dark-300">{paymentId.slice(0, 8)}</code>.
        </p>
      </>
    )
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="card max-w-lg w-full text-center space-y-4">
        {content}
        <div className="flex flex-wrap justify-center gap-3 pt-2">
          <Link to="/dashboard" className="btn-primary">Aller au dashboard</Link>
          <Link to="/pricing" className="btn-secondary">Voir les tarifs</Link>
        </div>
      </div>
    </div>
  )
}
