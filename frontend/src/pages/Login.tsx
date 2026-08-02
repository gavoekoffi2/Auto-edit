import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import Logo from '../components/ui/Logo'
import { login } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { toast } from '../components/ui/Toast'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const data = await login(email, password)
      setTokens(data.access_token, data.refresh_token)
      toast('success', 'Bon retour sur CutForge !')
      navigate('/dashboard')
    } catch (err: unknown) {
      let msg = 'Login failed'
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }, status?: number } }
        msg = axiosErr.response?.data?.detail || msg
        if (axiosErr.response?.status === 429) {
          msg = 'Too many login attempts. Please wait and try again.'
        }
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative isolate flex min-h-[82vh] items-center justify-center overflow-hidden px-4 py-12">
      <div className="absolute inset-0 -z-10" aria-hidden>
        <div className="halo left-[-10%] top-[-10%] h-[420px] w-[420px] bg-primary-700/35" />
        <div className="halo bottom-[-15%] right-[-8%] h-[380px] w-[380px] bg-iris-700/25" />
        <div className="cf-grid-dots absolute inset-0" />
      </div>
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 w-fit"><Logo size={46} /></div>
          <h1 className="text-title font-bold">Bon retour</h1>
          <p className="mt-2 text-sm text-dark-400">Connecte-toi à ton studio CutForge</p>
        </div>

        <form onSubmit={handleSubmit} className="panel space-y-4">
          {error && (
            <div className="rounded-xl border border-red-400/20 bg-red-400/[0.08] p-3 text-sm leading-relaxed text-red-300">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="mb-1.5 block text-xs font-medium text-dark-400">Email</label>
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
            <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-dark-400">Mot de passe</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="field"
              placeholder="Ton mot de passe"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="btn-primary flex w-full items-center justify-center gap-2" disabled={loading}>
            {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Se connecter'}
          </button>

          <div className="space-y-2 pt-1 text-center">
            <p className="text-sm text-dark-500">
              <Link to="/forgot-password" className="text-primary-300 transition-colors hover:text-primary-200">
                Mot de passe oublié ?
              </Link>
            </p>
            <p className="text-sm text-dark-500">
              Pas encore de compte ?{' '}
              <Link to="/signup" className="font-medium text-primary-300 transition-colors hover:text-primary-200">
                Créer un compte
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  )
}
