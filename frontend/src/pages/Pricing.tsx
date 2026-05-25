import { useState } from 'react'
import { Check, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import Footer from '../components/layout/Footer'

const plans = [
  {
    id: 'free',
    name: 'Free',
    price: { XOF: 0, USD: 0 },
    description: 'Découvre AutoEdit gratuitement',
    features: [
      '2 vidéos / mois',
      '5 min max par vidéo',
      'Pipeline V1 (silences + sous-titres)',
      'Export 720p',
      'Support communauté',
    ],
    cta: 'Commencer gratuitement',
    popular: false,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: { XOF: 5000, USD: 10 },
    description: 'Pour créateurs & entrepreneurs africains',
    features: [
      'Vidéos illimitées',
      '30 min max par vidéo',
      'Pipeline V2 IA (B-roll africain)',
      'Tous les modes (TikTok viral, Business premium…)',
      'Sous-titres dynamiques',
      'Musique + SFX',
      'Export 1080p 9:16',
      'Support prioritaire',
    ],
    cta: 'Passer Pro',
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: { XOF: 15000, USD: 30 },
    description: 'Pour agences & équipes',
    features: [
      'Tout illimité',
      'Aucune limite de durée',
      'Tous les modes IA',
      'Export 4K + 9:16 / 16:9 / 1:1',
      'Branding personnalisé',
      'Accès API',
      'Traitement par batch',
      'Support dédié',
    ],
    cta: 'Nous contacter',
    popular: false,
  },
]

export default function Pricing() {
  const [currency, setCurrency] = useState<'XOF' | 'USD'>('XOF')

  return (
    <div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Tarifs simples,
            <span className="gradient-text"> orientés Afrique</span>
          </h1>
          <p className="text-dark-400 text-lg max-w-2xl mx-auto mb-8">
            Démarre gratuitement. Passe Pro quand tu veux du B-roll IA et des
            captions dynamiques. Paiement Mobile Money via FedaPay.
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
                    <span className="text-dark-500 text-sm"> /mois</span>
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

              <Link
                to={plan.id === 'free' ? '/signup' : '/signup'}
                className={`block text-center py-3 rounded-lg font-semibold transition-all ${
                  plan.popular
                    ? 'btn-primary'
                    : 'btn-secondary'
                }`}
              >
                {plan.id === 'free' ? (
                  plan.cta
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <Zap className="w-4 h-4" />
                    {plan.cta}
                  </span>
                )}
              </Link>
            </div>
          ))}
        </div>

        {/* Modes inclus */}
        <div className="mt-20">
          <h2 className="text-2xl font-bold text-center mb-2">Modes inclus avec le plan Pro</h2>
          <p className="text-dark-400 text-center mb-8 text-sm max-w-xl mx-auto">
            Le pipeline V2 d&apos;AutoEdit est pensé pour le marché africain francophone — Togo, Bénin, Côte d&apos;Ivoire, Sénégal, Cameroun, RDC.
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
