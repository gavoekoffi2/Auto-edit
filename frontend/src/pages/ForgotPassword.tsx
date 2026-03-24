import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Zap, Loader2 } from 'lucide-react'
import client from '../api/client'
import { toast } from '../components/ui/Toast'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      await client.post('/auth/password-reset/request', { email })
      setSent(true)
      toast('success', 'If that email is registered, a reset link has been sent.')
    } catch {
      toast('error', 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Zap className="w-12 h-12 text-accent-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold">Reset your password</h1>
          <p className="text-dark-400 mt-2">
            Enter your email and we'll send you a reset link
          </p>
        </div>

        {sent ? (
          <div className="card text-center space-y-4">
            <p className="text-dark-300">
              Check your email for a password reset link. It will expire in 15 minutes.
            </p>
            <Link to="/login" className="btn-primary inline-block">
              Back to Login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-dark-300 mb-1">
                Email
              </label>
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

            <button
              type="submit"
              className="btn-primary w-full flex items-center justify-center gap-2"
              disabled={loading}
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send Reset Link'}
            </button>

            <p className="text-center text-dark-400 text-sm">
              Remember your password?{' '}
              <Link to="/login" className="text-primary-400 hover:underline">
                Log in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
