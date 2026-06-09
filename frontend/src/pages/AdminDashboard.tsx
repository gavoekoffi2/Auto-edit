import { useEffect, useMemo, useState } from 'react'
import { Shield, Loader2, Search, Crown, Calendar, CheckCircle, XCircle } from 'lucide-react'
import { grantSubscription, listAdminUsers, type AdminUser } from '../api/admin'
import { toast } from '../components/ui/Toast'

const quickDurations = [
  { label: 'Illimité', value: '' },
  { label: '7 jours', value: '7' },
  { label: '30 jours', value: '30' },
  { label: '90 jours', value: '90' },
  { label: '1 an', value: '365' },
]

function formatExpiry(value: string | null) {
  if (!value) return 'Permanent / illimité'
  return new Date(value).toLocaleDateString('fr-FR', { year: 'numeric', month: 'short', day: 'numeric' })
}

function planLabel(user: AdminUser) {
  if (user.effective_plan !== user.plan) return `${user.plan.toUpperCase()} expiré → FREE`
  return user.effective_plan.toUpperCase()
}

export default function AdminDashboard() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [q, setQ] = useState('')
  const [email, setEmail] = useState('')
  const [plan, setPlan] = useState<'free' | 'pro' | 'enterprise'>('enterprise')
  const [duration, setDuration] = useState('')
  const [makeAdmin, setMakeAdmin] = useState(false)
  const [activateAccount, setActivateAccount] = useState(true)
  const [createIfMissing, setCreateIfMissing] = useState(true)
  const [fullName, setFullName] = useState('')
  const [initialPassword, setInitialPassword] = useState('')
  const [lastTemporaryPassword, setLastTemporaryPassword] = useState<string | null>(null)

  const filtered = useMemo(() => users, [users])

  async function loadUsers(search = q) {
    setLoading(true)
    try {
      const data = await listAdminUsers(search)
      setUsers(data)
    } catch (err) {
      toast('error', 'Accès admin refusé ou chargement impossible')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function submitGrant(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const durationDays = duration.trim() ? Number(duration) : null
      const response = await grantSubscription({
        email,
        plan,
        duration_days: durationDays,
        create_if_missing: createIfMissing,
        initial_password: initialPassword.trim() || null,
        full_name: fullName.trim() || null,
        is_admin: makeAdmin ? true : null,
        is_active: activateAccount,
      })
      toast('success', response.message)
      setLastTemporaryPassword(response.temporary_password)
      setUsers((prev) => {
        const without = prev.filter((u) => u.id !== response.user.id)
        return [response.user, ...without]
      })
      setEmail('')
      setFullName('')
      setInitialPassword('')
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Impossible de modifier cet abonnement'
      toast('error', String(detail))
    } finally {
      setSaving(false)
    }
  }

  function fillUser(user: AdminUser) {
    setEmail(user.email)
    setPlan(user.plan as 'free' | 'pro' | 'enterprise')
    setDuration('')
    setMakeAdmin(user.is_admin)
    setActivateAccount(user.is_active)
    setCreateIfMissing(false)
    setFullName(user.full_name || '')
    setInitialPassword('')
    setLastTemporaryPassword(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-11 h-11 rounded-2xl bg-primary-500/15 flex items-center justify-center">
          <Shield className="w-6 h-6 text-primary-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold">Admin abonnements</h1>
          <p className="text-dark-400 mt-1">Donner Pro, Enterprise ou accès illimité à un compte par email.</p>
        </div>
      </div>

      <form onSubmit={submitGrant} className="card mb-8 grid gap-5 lg:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <label className="block text-sm text-dark-300 mb-2">Email du client</label>
          <input
            className="input w-full"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="client@email.com"
            required
          />
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Nom complet</label>
          <input
            className="input w-full"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Nom du client"
          />
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Mot de passe initial</label>
          <input
            className="input w-full"
            value={initialPassword}
            onChange={(e) => setInitialPassword(e.target.value)}
            placeholder="Vide = généré auto"
            type="text"
          />
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Abonnement</label>
          <select className="input w-full" value={plan} onChange={(e) => setPlan(e.target.value as any)}>
            <option value="enterprise">Enterprise — illimité</option>
            <option value="pro">Pro</option>
            <option value="free">Free</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Durée</label>
          <select className="input w-full" value={duration} onChange={(e) => setDuration(e.target.value)}>
            {quickDurations.map((d) => <option key={d.label} value={d.value}>{d.label}</option>)}
          </select>
        </div>

        <div className="lg:col-span-3 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
          <div className="flex flex-wrap gap-4 text-sm text-dark-300">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={createIfMissing} onChange={(e) => setCreateIfMissing(e.target.checked)} />
              Créer le compte s’il n’existe pas
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={activateAccount} onChange={(e) => setActivateAccount(e.target.checked)} />
              Compte actif
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={makeAdmin} onChange={(e) => setMakeAdmin(e.target.checked)} />
              Donner aussi accès admin
            </label>
          </div>
          <button className="btn-primary flex items-center justify-center gap-2" disabled={saving}>
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Crown className="w-4 h-4" />}
            Appliquer l’accès
          </button>
        </div>
        {lastTemporaryPassword && (
          <div className="lg:col-span-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
            Compte créé. Mot de passe temporaire à envoyer au client :
            <code className="ml-2 px-2 py-1 rounded bg-dark-900 text-amber-200">{lastTemporaryPassword}</code>
          </div>
        )}
      </form>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between mb-4">
        <h2 className="text-xl font-semibold">Utilisateurs</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); loadUsers(q) }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher email / nom" />
          <button className="btn-secondary flex items-center gap-2"><Search className="w-4 h-4" /> Chercher</button>
        </form>
      </div>

      {loading ? (
        <div className="text-center py-12"><Loader2 className="w-8 h-8 text-primary-500 animate-spin mx-auto" /></div>
      ) : filtered.length === 0 ? (
        <div className="card text-center text-dark-400">Aucun utilisateur trouvé.</div>
      ) : (
        <div className="grid gap-4">
          {filtered.map((user) => (
            <button key={user.id} onClick={() => fillUser(user)} className="card text-left hover:border-primary-500/50 transition-colors">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                  <div className="font-semibold flex items-center gap-2">
                    {user.email}
                    {user.is_admin && <span className="text-xs px-2 py-1 rounded-full bg-primary-500/15 text-primary-300">ADMIN</span>}
                  </div>
                  <div className="text-sm text-dark-500 mt-1">{user.full_name || 'Sans nom'} · {user.videos_count} vidéo(s)</div>
                </div>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="flex items-center gap-1 text-accent-300"><Crown className="w-4 h-4" /> {planLabel(user)}</span>
                  <span className="flex items-center gap-1 text-dark-300"><Calendar className="w-4 h-4" /> {formatExpiry(user.subscription_expires_at)}</span>
                  <span className={user.is_active ? 'text-emerald-400 flex items-center gap-1' : 'text-red-400 flex items-center gap-1'}>
                    {user.is_active ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    {user.is_active ? 'Actif' : 'Bloqué'}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
