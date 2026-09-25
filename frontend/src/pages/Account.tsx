import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Crown, KeyRound, Loader2, Receipt } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { changePassword, getMe } from '../api/auth'
import client, { getErrorMessage } from '../api/client'
import { toast } from '../components/ui/Toast'
import { BRAND } from '../brand'

interface PaymentRow {
  id: string
  amount: number
  currency: string
  status: 'pending' | 'completed' | 'failed'
  plan: string
  created_at: string
}

const PAYMENT_STATUS: Record<string, string> = {
  completed: 'Payé',
  pending: 'En attente',
  failed: 'Échoué',
}

export default function Account() {
  const { user, setUser, setTokens } = useAuthStore()
  const [payments, setPayments] = useState<PaymentRow[]>([])
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getMe().then(setUser).catch(() => {})
    client.get('/payments/history').then((r) => setPayments(r.data)).catch(() => {})
  }, [setUser])

  const plan = (user?.effective_plan || user?.plan || 'free').toLowerCase()

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (next.length < 8 || !/[A-Za-z]/.test(next) || !/[0-9]/.test(next)) {
      toast('error', 'Le nouveau mot de passe doit contenir 8 caractères min., dont une lettre et un chiffre.')
      return
    }
    if (next !== confirm) {
      toast('error', 'Les deux mots de passe ne correspondent pas.')
      return
    }
    setSaving(true)
    try {
      const tokens = await changePassword(current, next)
      setTokens(tokens.access_token, tokens.refresh_token)
      setCurrent('')
      setNext('')
      setConfirm('')
      toast('success', 'Mot de passe modifié. Tes autres sessions ont été déconnectées.')
    } catch (err) {
      toast('error', getErrorMessage(err, 'Modification impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <h1 className="text-3xl font-bold">Mon compte</h1>
      <p className="mt-1 text-dark-400">{user?.email}</p>

      <section className="card mt-8">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Crown className="h-5 w-5 text-amber-300" /> Abonnement
        </h2>
        <p className="mt-3 text-dark-300">
          Plan actuel : <strong className="text-white">{plan.toUpperCase()}</strong>
          {plan !== 'free' && user?.subscription_expires_at && (
            <> — actif jusqu&apos;au {new Date(user.subscription_expires_at).toLocaleDateString('fr-FR')}</>
          )}
          {plan !== 'free' && !user?.subscription_expires_at && <> — accès permanent</>}
        </p>
        {user?.plan && user.plan !== 'free' && plan === 'free' && (
          <p className="mt-2 text-sm text-amber-300">Ton abonnement {user.plan.toUpperCase()} a expiré.</p>
        )}
        <Link to="/pricing" className="btn-primary mt-4 inline-block text-sm">
          {plan === 'free' ? 'Passer Pro' : 'Prolonger / changer de plan'}
        </Link>
      </section>

      <section className="card mt-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Receipt className="h-5 w-5 text-primary-400" /> Paiements
        </h2>
        {payments.length === 0 ? (
          <p className="mt-3 text-sm text-dark-400">Aucun paiement pour l&apos;instant.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-dark-400">
                <tr>
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Plan</th>
                  <th className="py-2 pr-4 font-medium">Montant</th>
                  <th className="py-2 font-medium">Statut</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-t border-white/5">
                    <td className="py-2 pr-4">{new Date(p.created_at).toLocaleDateString('fr-FR')}</td>
                    <td className="py-2 pr-4">{p.plan.toUpperCase()}</td>
                    <td className="py-2 pr-4">{p.amount.toLocaleString('fr-FR')} {p.currency === 'XOF' ? 'FCFA' : p.currency}</td>
                    <td className="py-2">{PAYMENT_STATUS[p.status] ?? p.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card mt-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <KeyRound className="h-5 w-5 text-primary-400" /> Changer de mot de passe
        </h2>
        <form onSubmit={handleChangePassword} className="mt-4 space-y-3">
          <input
            type="password"
            className="input-field"
            placeholder="Mot de passe actuel"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            autoComplete="current-password"
          />
          <input
            type="password"
            className="input-field"
            placeholder="Nouveau mot de passe"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            minLength={8}
            required
            autoComplete="new-password"
          />
          <input
            type="password"
            className="input-field"
            placeholder="Confirmer le nouveau mot de passe"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            minLength={8}
            required
            autoComplete="new-password"
          />
          <button type="submit" className="btn-secondary flex items-center gap-2" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Enregistrer
          </button>
        </form>
      </section>

      <p className="mt-8 text-sm text-dark-500">
        Besoin d&apos;aide ou envie de supprimer ton compte ? Écris-nous à{' '}
        <a href={`mailto:${BRAND.supportEmail}`} className="text-primary-400 hover:underline">{BRAND.supportEmail}</a>.
      </p>
    </div>
  )
}
