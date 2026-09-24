import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, MailCheck } from 'lucide-react'
import Logo from '../components/ui/Logo'
import { requestPasswordReset } from '../api/auth'
import { getApiErrorMessage } from '../api/errors'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      setError(getApiErrorMessage(err, "Impossible d'envoyer le lien. Réessaie."))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 w-fit"><Logo size={48} /></div>
          <h1 className="text-2xl font-bold">Mot de passe oublié</h1>
          <p className="text-dark-400 mt-2">
            Indique ton email : on t'envoie un lien pour en choisir un nouveau.
          </p>
        </div>

        {sent ? (
          <div className="card text-center space-y-4">
            <MailCheck className="w-10 h-10 text-emerald-400 mx-auto" />
            <p className="text-dark-300">
              Si un compte existe avec <strong>{email}</strong>, un lien de réinitialisation
              vient d'être envoyé. Il expire dans 15 minutes. Pense à vérifier tes spams.
            </p>
            <Link to="/login" className="btn-primary inline-block">
              Retour à la connexion
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card space-y-4">
            {error && (
              <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm">
                {error}
              </div>
            )}
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
                placeholder="toi@exemple.com"
                required
                autoComplete="email"
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full flex items-center justify-center gap-2"
              disabled={loading}
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Envoyer le lien'}
            </button>

            <p className="text-center text-dark-400 text-sm">
              Tu t'en souviens ?{' '}
              <Link to="/login" className="text-primary-400 hover:underline">
                Se connecter
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
