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
    <div className="relative isolate min-h-[80vh] flex items-center justify-center overflow-hidden px-4">
      <div className="absolute inset-0 -z-10" aria-hidden>
        <div className="cf-aurora left-[-10%] top-[-10%] h-[380px] w-[380px] bg-primary-600/40" />
        <div className="cf-aurora right-[-8%] bottom-[-15%] h-[340px] w-[340px] bg-accent-500/25" style={{ animationDelay: '-8s' }} />
        <div className="cf-grid-dots absolute inset-0" />
      </div>
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 w-fit"><Logo size={48} /></div>
          <h1 className="text-2xl font-bold">Bon retour 👋</h1>
          <p className="text-dark-400 mt-2">Connecte-toi à ton compte CutForge</p>
        </div>

        <form onSubmit={handleSubmit} className="card glass space-y-4">
          {error && (
            <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-dark-300 mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              placeholder="you@example.com"
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
              className="input-field"
              placeholder="Ton mot de passe"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Se connecter'}
          </button>

          <div className="text-center space-y-2">
            <p className="text-dark-400 text-sm">
              <Link to="/forgot-password" className="text-primary-400 hover:underline">
                Mot de passe oublié ?
              </Link>
            </p>
            <p className="text-dark-400 text-sm">
              Pas encore de compte ?{' '}
              <Link to="/signup" className="text-primary-400 hover:underline">
                Créer un compte
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  )
}
