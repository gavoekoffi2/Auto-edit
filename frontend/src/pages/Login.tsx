import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Zap, Loader2 } from 'lucide-react'
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
      toast('success', 'Welcome back!')
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
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Zap className="w-12 h-12 text-accent-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold">Welcome back</h1>
          <p className="text-dark-400 mt-2">Log in to your AutoEdit account</p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4">
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
            <label htmlFor="password" className="block text-sm font-medium text-dark-300 mb-1">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              placeholder="Your password"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Log In'}
          </button>

          <div className="text-center space-y-2">
            <p className="text-dark-400 text-sm">
              <Link to="/forgot-password" className="text-primary-400 hover:underline">
                Forgot your password?
              </Link>
            </p>
            <p className="text-dark-400 text-sm">
              Don't have an account?{' '}
              <Link to="/signup" className="text-primary-400 hover:underline">
                Sign up
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  )
}
