import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import Logo from '../components/ui/Logo'
import { signup } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { toast } from '../components/ui/Toast'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // Client-side validation
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      setLoading(false)
      return
    }
    if (!/[0-9]/.test(password)) {
      setError('Password must contain at least one number')
      setLoading(false)
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      setLoading(false)
      return
    }

    try {
      const data = await signup(email, password, fullName || undefined)
      setTokens(data.access_token, data.refresh_token)
      toast('success', 'Compte créé ! Bienvenue sur CutForge.')
      navigate('/dashboard')
    } catch (err: unknown) {
      let msg = 'Signup failed'
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string | { msg: string }[] } } }
        const detail = axiosErr.response?.data?.detail
        if (typeof detail === 'string') {
          msg = detail
        } else if (Array.isArray(detail)) {
          msg = detail.map((d) => d.msg).join('. ')
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
          <h1 className="text-2xl font-bold">Crée ton compte</h1>
          <p className="text-dark-400 mt-2">2 montages offerts par mois — sans carte bancaire</p>
        </div>

        <form onSubmit={handleSubmit} className="card glass space-y-4">
          {error && (
            <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-dark-300 mb-1">Full Name</label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="input-field"
              placeholder="John Doe"
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
              className="input-field"
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-dark-300 mb-1">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              placeholder="Min 8 characters, include a number"
              minLength={8}
              required
              autoComplete="new-password"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-dark-300 mb-1">Confirm Password</label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="input-field"
              placeholder="Re-enter your password"
              minLength={8}
              required
              autoComplete="new-password"
            />
          </div>

          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Create Account'}
          </button>

          <p className="text-center text-dark-400 text-sm">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-400 hover:underline">
              Log in
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
