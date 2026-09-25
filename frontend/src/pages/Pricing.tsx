import { useEffect, useState } from 'react'
import { Check, Loader2, Zap } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Footer from '../components/layout/Footer'
import { createCheckout, getPlans, type PlanDescriptor } from '../api/payments'
import { getErrorMessage } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { toast } from '../components/ui/Toast'

interface DisplayPlan extends PlanDescriptor {
  description: string
  cta: string
  popular: boolean
}

const PLAN_COPY: Record<string, { description: string; cta: string; popular: boolean }> = {
  free: { description: 'Découvre CutForge gratuitement', cta: 'Commencer gratuitement', popular: false },
  pro: { description: 'Pour créateurs & entrepreneurs africains', cta: 'Passer Pro', popular: true },
  enterprise: { description: 'Pour agences & équipes', cta: 'Passer Enterprise', popular: false },
}

// Repli si l'API est injoignable — la source de vérité est GET /payments/plans
// (quotas réellement appliqués par le backend).
const FALLBACK_PLANS: PlanDescriptor[] = [
  { id: 'free', name: 'Free', price: { XOF: 0, USD: 0 }, features: ['2 vidéos / mois', '15 min max par vidéo', 'Tous les styles de montage'] },
  { id: 'pro', name: 'Pro', price: { XOF: 5000, USD: 10 }, features: ['Vidéos illimitées', '60 min max par vidéo', 'Tous les styles + B-roll IA', 'Support prioritaire'] },
  { id: 'enterprise', name: 'Enterprise', price: { XOF: 15000, USD: 30 }, features: ['Vidéos illimitées', 'Aucune limite de durée', 'Support dédié'] },
]

function withCopy(list: PlanDescriptor[]): DisplayPlan[] {
  return list.map((p) => ({ ...p, ...(PLAN_COPY[p.id] ?? PLAN_COPY.free) }))
}

export default function Pricing() {
  const [currency, setCurrency] = useState<'XOF' | 'USD'>('XOF')
  const [plans, setPlans] = useState<DisplayPlan[]>(withCopy(FALLBACK_PLANS))
  const [days, setDays] = useState(30)
  const [paymentsEnabled, setPaymentsEnabled] = useState(true)
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const token = useAuthStore((s) => s.accessToken)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const currentPlan = (user?.effective_plan || user?.plan || 'free').toLowerCase()

  useEffect(() => {
    getPlans()
      .then((data) => {
        if (data?.plans?.length) setPlans(withCopy(data.plans))
        if (data?.subscription_days) setDays(data.subscription_days)
        if (typeof data?.payments_enabled === 'boolean') setPaymentsEnabled(data.payments_enabled)
      })
      .catch(() => { /* repli statique */ })
  }, [])

  const handleChoose = async (planId: string) => {
    if (planId === 'free') {
      navigate(token ? '/dashboard' : '/signup')
      return
    }
    if (!token) {
      navigate(`/signup?plan=${planId}`)
      return
    }
    setBusyPlan(planId)
    try {
      const { checkout_url } = await createCheckout(planId, currency)
      window.location.assign(checkout_url)
    } catch (err) {
      toast('error', getErrorMessage(err, 'Impossible de démarrer le paiement. Réessaie.'))
      setBusyPlan(null)
    }
  }

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
            Paiement Mobile Money ou carte via FedaPay, sans engagement.
          </p>

          {/* Currency Toggle */}
          <div className="inline-flex bg-dark-800 rounded-lg p-1">
            <button
              onClick={() => setCurrency('XOF')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                currency === 'XOF' ? 'bg-primary-600 text-white' : 'text-dark-400 hover:text-white'
              }`}
            >
              XOF (FCFA)
            </button>
            <button
              onClick={() => setCurrency('USD')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                currency === 'USD' ? 'bg-primary-600 text-white' : 'text-dark-400 hover:text-white'
              }`}
            >
              USD ($)
            </button>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`card relative ${
                plan.popular ? 'border-primary-500 shadow-xl shadow-primary-500/10' : ''
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-primary-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    LE PLUS POPULAIRE
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-xl font-bold">{plan.name}</h3>
                <p className="text-dark-400 text-sm mt-1">{plan.description}</p>
                <div className="mt-4">
                  <span className="text-4xl font-bold">
                    {currency === 'XOF'
                      ? `${plan.price.XOF.toLocaleString()} FCFA`
                      : `$${plan.price.USD}`}
                  </span>
                  {plan.price.XOF > 0 && (
                    <span className="text-dark-500 text-sm"> / {days} jours</span>
                  )}
                </div>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <span className="text-dark-300">{feature}</span>
                  </li>
                ))}
              </ul>

              {token && plan.id === currentPlan && plan.id !== 'free' && user?.subscription_expires_at && (
                <p className="mb-3 text-center text-xs text-emerald-300">
                  Actif jusqu&apos;au {new Date(user.subscription_expires_at).toLocaleDateString('fr-FR')} — un paiement prolonge de {days} jours
                </p>
              )}
              <button
                type="button"
                onClick={() => handleChoose(plan.id)}
                disabled={busyPlan !== null || (plan.id !== 'free' && token !== null && !paymentsEnabled)}
                className={`w-full block text-center py-3 rounded-lg font-semibold transition-all disabled:opacity-60 ${
                  plan.popular
                    ? 'btn-primary'
                    : 'btn-secondary'
                }`}
              >
                {plan.id === 'free' ? (
                  token ? 'Aller au dashboard' : plan.cta
                ) : busyPlan === plan.id ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Redirection vers le paiement…
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <Zap className="w-4 h-4" />
                    {token && !paymentsEnabled ? 'Paiement bientôt disponible' : plan.cta}
                  </span>
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Modes inclus */}
        <div className="mt-20">
          <h2 className="text-2xl font-bold text-center mb-2">Styles de montage inclus dans tous les plans</h2>
          <p className="text-dark-400 text-center mb-8 text-sm max-w-xl mx-auto">
            Le moteur CutForge est pensé pour le marché africain francophone — Togo, Bénin, Côte d&apos;Ivoire, Sénégal, Cameroun, RDC.
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 max-w-5xl mx-auto">
            {[
              { icon: '🔥', name: 'TikTok viral', desc: 'Captions animées, CTA' },
              { icon: '💼', name: 'Business premium', desc: 'B-roll Afrique premium' },
              { icon: '📣', name: 'Publicité locale', desc: 'Restaurant, boutique…' },
              { icon: '🎙️', name: 'Podcast propre', desc: 'Silences nettoyés' },
              { icon: '🎓', name: 'Formation', desc: 'B-roll discret, 16:9' },
            ].map((m) => (
              <div key={m.name} className="bg-dark-800/50 border border-dark-700 rounded-lg p-4 text-center">
                <div className="text-3xl mb-2">{m.icon}</div>
                <p className="font-semibold text-sm">{m.name}</p>
                <p className="text-xs text-dark-400 mt-1">{m.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Payment Methods */}
        <div className="text-center mt-16">
          <p className="text-dark-500 text-sm mb-4">Moyens de paiement acceptés</p>
          <div className="flex items-center justify-center gap-6 text-dark-400 flex-wrap">
            <span className="bg-dark-800 px-4 py-2 rounded-lg text-sm">Mobile Money</span>
            <span className="bg-dark-800 px-4 py-2 rounded-lg text-sm">Visa / Mastercard</span>
            <span className="bg-dark-800 px-4 py-2 rounded-lg text-sm">FedaPay</span>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  )
}
