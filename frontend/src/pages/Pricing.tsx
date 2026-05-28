import { useState } from 'react'
import { Check, Zap, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Footer from '../components/layout/Footer'
import { createCheckout } from '../api/payments'
import { useAuthStore } from '../store/authStore'
import { toast } from '../components/ui/Toast'

const plans = [
  {
    id: 'free',
    name: 'Free',
    price: { XOF: 0, USD: 0 },
    description: 'Get started with basic editing',
    features: [
      '2 videos per month',
      'Max 5 min video',
      'Basic editing pipeline',
      '720p export',
      'Community support',
    ],
    cta: 'Start Free',
    popular: false,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: { XOF: 5000, USD: 10 },
    description: 'For content creators',
    features: [
      'Unlimited videos',
      'Max 30 min video',
      'All AI editing modes',
      '1080p export',
      'Subtitle generation',
      'Priority processing',
      'Email support',
    ],
    cta: 'Go Pro',
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: { XOF: 15000, USD: 30 },
    description: 'For teams and agencies',
    features: [
      'Unlimited everything',
      'No duration limit',
      'All AI modes',
      '4K export',
      'Custom branding',
      'API access',
      'Batch processing',
      'Dedicated support',
    ],
    cta: 'Contact Us',
    popular: false,
  },
]

export default function Pricing() {
  const [currency, setCurrency] = useState<'XOF' | 'USD'>('XOF')
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const navigate = useNavigate()
  const accessToken = useAuthStore((s) => s.accessToken)

  const handleSelectPlan = async (planId: string) => {
    // Free plan → just sign up.
    if (planId === 'free') {
      navigate('/signup')
      return
    }
    // Enterprise → sales contact.
    if (planId === 'enterprise') {
      window.location.href = 'mailto:sales@autoedit.app?subject=Enterprise%20plan'
      return
    }
    // Paid plan: require auth, then start a real checkout.
    if (!accessToken) {
      navigate('/signup?next=/pricing')
      return
    }
    setLoadingPlan(planId)
    try {
      const { checkout_url } = await createCheckout(planId, currency)
      if (checkout_url) {
        window.location.href = checkout_url
      } else {
        toast('error', 'Could not start checkout. Please try again.')
      }
    } catch (err: unknown) {
      let msg = 'Checkout failed. Please try again.'
      if (err && typeof err === 'object' && 'response' in err) {
        msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || msg
      }
      toast('error', msg)
    } finally {
      setLoadingPlan(null)
    }
  }

  return (
    <div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Simple, Transparent
            <span className="gradient-text"> Pricing</span>
          </h1>
          <p className="text-dark-400 text-lg max-w-2xl mx-auto mb-8">
            Start free. Upgrade when you need more power. Pay with Mobile Money.
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
                    MOST POPULAR
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
                    <span className="text-dark-500 text-sm"> /month</span>
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

              <button
                onClick={() => handleSelectPlan(plan.id)}
                disabled={loadingPlan === plan.id}
                className={`block w-full text-center py-3 rounded-lg font-semibold transition-all disabled:opacity-60 ${
                  plan.popular ? 'btn-primary' : 'btn-secondary'
                }`}
              >
                {loadingPlan === plan.id ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Redirecting...
                  </span>
                ) : plan.id === 'free' ? (
                  plan.cta
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <Zap className="w-4 h-4" />
                    {plan.cta}
                  </span>
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Payment Methods */}
        <div className="text-center mt-16">
          <p className="text-dark-500 text-sm mb-4">Accepted payment methods</p>
          <div className="flex items-center justify-center gap-6 text-dark-400">
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
