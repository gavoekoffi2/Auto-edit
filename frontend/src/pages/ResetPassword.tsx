import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import Logo from '../components/ui/Logo'
import { confirmPasswordReset } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { toast } from '../components/ui/Toast'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password.length < 8 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
      setError('Le mot de passe doit contenir au moins 8 caractères, dont une lettre et un chiffre.')
      return
    }
    if (password !== confirm) {
      setError('Les deux mots de passe ne correspondent pas.')
      return
    }
    setLoading(true)
    try {
      await confirmPasswordReset(token, password)
      toast('success', 'Mot de passe modifié. Connecte-toi avec ton nouveau mot de passe.')
      navigate('/login')
    } catch (err) {
      setError(getErrorMessage(err, 'Lien invalide ou expiré.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 w-fit"><Logo size={48} /></div>
          <h1 className="text-2xl font-bold">Nouveau mot de passe</h1>
          <p className="text-dark-400 mt-2">Choisis un nouveau mot de passe pour ton compte.</p>
        </div>

        {!token ? (
          <div className="card text-center space-y-4">
            <p className="text-dark-300">Ce lien est incomplet. Refais une demande de réinitialisation.</p>
            <Link to="/forgot-password" className="btn-primary inline-block">Nouvelle demande</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="card space-y-4">
            {error && (
              <div className="bg-red-400/10 border border-red-400/20 rounded-lg p-3 text-red-400 text-sm">
                {error}
                {/expir|invalide/i.test(error) && (
                  <>
                    {' '}
                    <Link to="/forgot-password" className="underline">Refaire une demande</Link>
                  </>
                )}
              </div>
            )}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-dark-300 mb-1">Nouveau mot de passe</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="8 caractères min., lettres et chiffres"
                minLength={8}
                required
                autoComplete="new-password"
              />
            </div>
            <div>
              <label htmlFor="confirm" className="block text-sm font-medium text-dark-300 mb-1">Confirmer</label>
              <input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="input-field"
                placeholder="Retape le mot de passe"
                minLength={8}
                required
                autoComplete="new-password"
              />
            </div>
            <button type="submit" className="btn-primary w-full flex items-center justify-center gap-2" disabled={loading}>
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Enregistrer le mot de passe'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
