import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import Logo from '../components/ui/Logo'
import { signup } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { toast } from '../components/ui/Toast'
import { getErrorMessage } from '../api/client'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)
  const [searchParams] = useSearchParams()
  const wantedPlan = searchParams.get('plan')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // Client-side validation
    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères')
      setLoading(false)
      return
    }
    if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
      setError('Le mot de passe doit contenir au moins une lettre et un chiffre')
      setLoading(false)
      return
    }
    if (password !== confirmPassword) {
      setError('Les deux mots de passe ne correspondent pas')
      setLoading(false)
      return
    }

    try {
      const data = await signup(email, password, fullName || undefined)
      setTokens(data.access_token, data.refresh_token)
      toast('success', 'Compte créé ! Bienvenue sur CutForge.')
      navigate(wantedPlan ? '/pricing' : '/dashboard')
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Impossible de créer le compte. Réessaie."))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative isolate min-h-[80vh] flex items-center justify-center overflow-hidden px-4">
      <div className="absolute inset-0 -z-10" aria-hidden>
        <div className="halo left-[-10%] top-[-10%] h-[420px] w-[420px] bg-primary-700/35" />
        <div className="halo bottom-[-15%] right-[-8%] h-[380px] w-[380px] bg-iris-700/25" />
        <div className="cf-grid-dots absolute inset-0" />
      </div>
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 w-fit"><Logo size={48} /></div>
          <h1 className="text-title font-bold">Crée ton compte</h1>
          <p className="text-dark-400 mt-2">2 montages offerts par mois — sans carte bancaire</p>
        </div>

        <form onSubmit={handleSubmit} className="panel space-y-4">
          {error && (
            <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-dark-300 mb-1">Nom complet</label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="field"
              placeholder="Ex : Awa Koné"
              autoComplete="name"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-dark-300 mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="field"
              placeholder="toi@exemple.com"
              required
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-dark-300 mb-1">Mot de passe</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="field"
              placeholder="8 caractères min., lettres et chiffres"
              minLength={8}
              required
              autoComplete="new-password"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-dark-300 mb-1">Confirmer le mot de passe</label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="field"
              placeholder="Retape ton mot de passe"
              minLength={8}
              required
              autoComplete="new-password"
            />
          </div>

          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Créer mon compte'}
          </button>

          <p className="text-center text-dark-500 text-xs">
            En créant un compte, tu acceptes les{' '}
            <Link to="/terms" className="underline hover:text-white">CGU</Link> et la{' '}
            <Link to="/privacy" className="underline hover:text-white">politique de confidentialité</Link>.
          </p>

          <p className="text-center text-dark-400 text-sm">
            Déjà un compte ?{' '}
            <Link to="/login" className="text-primary-400 hover:underline">
              Se connecter
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
