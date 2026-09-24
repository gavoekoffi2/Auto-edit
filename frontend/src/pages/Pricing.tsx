import { useEffect, useState } from 'react'
import { Check, Crown, Loader2, Zap } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import Footer from '../components/layout/Footer'
import { createCheckout, getPlans, type PlanInfo } from '../api/payments'
import { getApiErrorMessage } from '../api/errors'
import { useAuthStore } from '../store/authStore'
import { toast } from '../components/ui/Toast'

type PlanId = PlanInfo['id']

// Repli si l'API est injoignable. Les limites RÉELLES viennent de
// `GET /payments/plans` (mêmes valeurs que celles appliquées par le backend).
const FALLBACK_PLANS: PlanInfo[] = [
  { id: 'free', name: 'Gratuit', price: { XOF: 0, USD: 0 },
    limits: { montages_per_month: 2, max_video_minutes: 15, concurrent_jobs: 2, clips_per_job: 3 } },
  { id: 'pro', name: 'Pro', price: { XOF: 5000, USD: 10 },
    limits: { montages_per_month: null, max_video_minutes: 60, concurrent_jobs: 5, clips_per_job: 10 } },
  { id: 'enterprise', name: 'Enterprise', price: { XOF: 15000, USD: 30 },
    limits: { montages_per_month: null, max_video_minutes: null, concurrent_jobs: null, clips_per_job: 100 } },
]

const DESCRIPTIONS: Record<PlanId, string> = {
  free: 'Découvre CutForge gratuitement',
  pro: 'Pour créateurs & entrepreneurs',
  enterprise: 'Pour agences & équipes',
}

function featuresFor(plan: PlanInfo): string[] {
  const l = plan.limits
  const list = [
    l.montages_per_month ? `${l.montages_per_month} montages / mois` : 'Montages illimités',
    l.max_video_minutes ? `Vidéos jusqu'à ${l.max_video_minutes} min` : 'Aucune limite de durée',
    l.concurrent_jobs ? `${l.concurrent_jobs} montages en parallèle` : 'Montages en parallèle illimités',
    `Jusqu'à ${l.clips_per_job} clips par vidéo longue`,
    'Tous les styles de montage',
    'Sous-titres animés, SFX, musique, motion design',
    'Export MP4 9:16 prêt pour TikTok / Reels',
  ]
  if (plan.id === 'pro') list.push('Support prioritaire')
  if (plan.id === 'enterprise') list.push('Support dédié')
  return list
}

function formatPrice(plan: PlanInfo, currency: 'XOF' | 'USD') {
  return currency === 'XOF' ? `${plan.price.XOF.toLocaleString('fr-FR')} FCFA` : `$${plan.price.USD}`
}

export default function Pricing() {
  const [currency, setCurrency] = useState<'XOF' | 'USD'>('XOF')
  const [plans, setPlans] = useState<PlanInfo[]>(FALLBACK_PLANS)
  const [periodDays, setPeriodDays] = useState(30)
  const [paying, setPaying] = useState<PlanId | null>(null)
  const { accessToken, user } = useAuthStore()
  const navigate = useNavigate()
  const currentPlan = (user?.effective_plan || user?.plan || 'free') as PlanId

  useEffect(() => {
    getPlans()
      .then((data) => {
        if (data.plans?.length) setPlans(data.plans)
        if (data.period_days) setPeriodDays(data.period_days)
      })
      .catch(() => { /* on garde le repli */ })
  }, [])

  const handleSelect = async (plan: PlanInfo) => {
    if (plan.id === 'free') {
      navigate(accessToken ? '/dashboard' : '/signup')
      return
    }
    if (!accessToken) {
      navigate(`/signup?next=${encodeURIComponent('/pricing')}`)
      return
    }
    setPaying(plan.id)
    try {
      // Le paiement est toujours encaissé en FCFA (Mobile Money / carte via
      // FedaPay); l'affichage en dollars est indicatif.
      const { checkout_url } = await createCheckout(plan.id, 'XOF')
      window.location.href = checkout_url
    } catch (err) {
      toast('error', getApiErrorMessage(err, 'Impossible de lancer le paiement. Réessaie.'))
      setPaying(null)
    }
  }

  const expires = user?.subscription_expires_at
    ? new Date(user.subscription_expires_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
    : null

  return (
    <div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Tarifs simples,
            <span className="gradient-text"> orientés Afrique</span>
          </h1>
          <p className="text-dark-400 text-lg max-w-2xl mx-auto mb-8">
            Démarre gratuitement. Passe Pro quand tu veux monter sans limite.
            Paiement Mobile Money ou carte via FedaPay — sans engagement, {periodDays} jours par paiement.
          </p>

          {accessToken && currentPlan !== 'free' && (
            <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-amber-300/40 bg-amber-300/10 px-4 py-1.5 text-sm text-amber-200">
              <Crown className="h-4 w-4" />
              Plan {currentPlan.toUpperCase()} actif{expires ? ` jusqu'au ${expires}` : ''}
            </p>
          )}

          {/* Currency Toggle */}
          <div className="flex flex-col items-center gap-2">
            <div className="inline-flex bg-dark-800 rounded-lg p-1">
              {(['XOF', 'USD'] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => setCurrency(c)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    currency === c ? 'bg-primary-600 text-white' : 'text-dark-400 hover:text-white'
                  }`}
                >
                  {c === 'XOF' ? 'XOF (FCFA)' : 'USD ($)'}
                </button>
              ))}
            </div>
            {currency === 'USD' && (
              <p className="text-xs text-dark-500">Montant indicatif — le paiement est encaissé en FCFA.</p>
            )}
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan) => {
            const popular = plan.id === 'pro'
            const isCurrent = accessToken && plan.id === currentPlan
            const busy = paying === plan.id
            let cta = 'Commencer gratuitement'
            if (plan.id !== 'free') {
              cta = isCurrent ? `Prolonger de ${periodDays} jours` : plan.id === 'pro' ? 'Passer Pro' : 'Passer Enterprise'
            } else if (accessToken) {
              cta = 'Aller au dashboard'
            }
            return (
              <div
                key={plan.id}
                className={`card relative ${popular ? 'border-primary-500 shadow-xl shadow-primary-500/10' : ''}`}
              >
                {popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-primary-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                      LE PLUS POPULAIRE
                    </span>
                  </div>
                )}

                <div className="text-center mb-6">
                  <h3 className="text-xl font-bold">{plan.name}</h3>
                  <p className="text-dark-400 text-sm mt-1">{DESCRIPTIONS[plan.id]}</p>
                  <div className="mt-4">
                    <span className="text-4xl font-bold">{formatPrice(plan, currency)}</span>
                    {plan.price.XOF > 0 && <span className="text-dark-500 text-sm"> / {periodDays} jours</span>}
                  </div>
                  {isCurrent && (
                    <span className="mt-3 inline-block rounded-full bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-300">
                      Ton plan actuel
                    </span>
                  )}
                </div>

                <ul className="space-y-3 mb-8">
                  {featuresFor(plan).map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span className="text-dark-300">{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSelect(plan)}
                  disabled={paying !== null}
                  className={`w-full text-center py-3 rounded-lg font-semibold transition-all disabled:opacity-60 ${
                    popular ? 'btn-primary' : 'btn-secondary'
                  }`}
                >
                  <span className="flex items-center justify-center gap-2">
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : plan.id !== 'free' && <Zap className="w-4 h-4" />}
                    {busy ? 'Redirection vers le paiement…' : cta}
                  </span>
                </button>
              </div>
            )
          })}
        </div>

        {/* Payment Methods */}
        <div className="text-center mt-16">
          <p className="text-dark-500 text-sm mb-4">Moyens de paiement acceptés</p>
          <div className="flex items-center justify-center gap-6 text-dark-400 flex-wrap">
            <span className="bg-dark-800 px-4 py-2 rounded-lg text-sm">Mobile Money</span>
            <span className="bg-dark-800 px-4 py-2 rounded-lg text-sm">Visa / Mastercard</span>
            <span className="bg-dark-800 px-4 py-2 rounded-lg text-sm">FedaPay</span>
          </div>
          <p className="text-dark-500 text-xs mt-6">
            Pas de renouvellement automatique : chaque paiement ajoute {periodDays} jours à ton abonnement.{' '}
            <Link to="/terms" className="underline hover:text-dark-300">Conditions</Link>
          </p>
        </div>
      </div>

      <Footer />
    </div>
  )
}
