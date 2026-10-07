import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import Logo from '../components/ui/Logo'
import client, { getErrorMessage } from '../api/client'
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
      toast('success', 'Si cet email correspond à un compte, un lien vient d’être envoyé.')
    } catch (err) {
      toast('error', getErrorMessage(err, 'Une erreur est survenue. Réessaie.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 w-fit"><Logo size={48} /></div>
          <h1 className="text-title font-bold">Mot de passe oublié</h1>
          <p className="text-dark-400 mt-2">
            Entre ton email : nous t’envoyons un lien pour choisir un nouveau mot de passe
          </p>
        </div>

        {sent ? (
          <div className="card text-center space-y-4">
            <p className="text-dark-300">
              Vérifie ta boîte mail (et les spams) : le lien est valable 1 heure.
            </p>
            <Link to="/login" className="btn-primary inline-block">
              Retour à la connexion
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
                className="field"
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
              Tu te souviens de ton mot de passe ?{' '}
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
