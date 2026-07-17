import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ban,
  Calendar,
  CheckCircle,
  Crown,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  Users,
  Video,
  XCircle,
} from 'lucide-react'
import {
  activateUser,
  deactivateUser,
  deleteUser,
  getAdminStats,
  grantSubscription,
  listAdminUsers,
  type AdminStats,
  type AdminUser,
} from '../api/admin'
import { toast } from '../components/ui/Toast'
import { useAuthStore } from '../store/authStore'

const quickDurations = [
  { label: 'Illimité / permanent', value: '' },
  { label: '7 jours', value: '7' },
  { label: '30 jours', value: '30' },
  { label: '90 jours', value: '90' },
  { label: '1 an', value: '365' },
]

function formatExpiry(value: string | null) {
  if (!value) return 'Permanent / illimité'
  return new Date(value).toLocaleDateString('fr-FR', { year: 'numeric', month: 'short', day: 'numeric' })
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('fr-FR').format(value || 0) + ' XOF'
}

function planLabel(user: AdminUser) {
  if (user.is_super_admin) return 'SUPER-ADMIN — SANS RESTRICTION'
  if (user.effective_plan !== user.plan) return `${user.plan.toUpperCase()} expiré → FREE`
  if (user.effective_plan === 'enterprise') return 'ENTERPRISE — ILLIMITÉ'
  return user.effective_plan.toUpperCase()
}

function videoLimitLabel(user: AdminUser) {
  if (user.effective_video_duration_limit_s === null) return 'Vidéo : durée illimitée'
  const hours = user.effective_video_duration_limit_s / 3600
  if (hours < 1) return `Vidéo : ${Math.round(hours * 60)} min`
  return `Vidéo : ${Number(hours.toFixed(2))} h`
}

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: any }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-dark-400">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <div className="w-11 h-11 rounded-2xl bg-primary-500/15 flex items-center justify-center">
          <Icon className="w-5 h-5 text-primary-300" />
        </div>
      </div>
    </div>
  )
}

export default function AdminDashboard() {
  const currentUser = useAuthStore((s) => s.user)
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [q, setQ] = useState('')
  const [email, setEmail] = useState('c1domefa@gmail.com')
  const [plan, setPlan] = useState<'free' | 'pro' | 'enterprise'>('enterprise')
  const [duration, setDuration] = useState('')
  // Vide = règle du plan, 0 = illimité, valeur positive = heures par vidéo.
  const [videoHours, setVideoHours] = useState('0')
  const [makeAdmin, setMakeAdmin] = useState(true)
  const [activateAccount, setActivateAccount] = useState(true)
  const [createIfMissing, setCreateIfMissing] = useState(true)
  const [fullName, setFullName] = useState('')
  const [initialPassword, setInitialPassword] = useState('')
  const [lastTemporaryPassword, setLastTemporaryPassword] = useState<string | null>(null)

  const filtered = useMemo(() => users, [users])

  async function loadAll(search = q) {
    setLoading(true)
    try {
      const [statsData, usersData] = await Promise.all([getAdminStats(), listAdminUsers(search)])
      setStats(statsData)
      setUsers(usersData)
    } catch (err) {
      toast('error', 'Accès admin refusé ou chargement impossible')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function replaceUser(user: AdminUser) {
    setUsers((prev) => {
      const without = prev.filter((u) => u.id !== user.id)
      return [user, ...without]
    })
  }

  async function submitGrant(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const durationDays = duration.trim() ? Number(duration) : null
      const videoDurationMinutes = videoHours.trim() === ''
        ? null
        : Math.round(Number(videoHours) * 60)
      const response = await grantSubscription({
        email,
        plan,
        duration_days: durationDays,
        create_if_missing: createIfMissing,
        initial_password: initialPassword.trim() || null,
        full_name: fullName.trim() || null,
        is_admin: makeAdmin,
        is_active: activateAccount,
        video_duration_limit_minutes: videoDurationMinutes,
      })
      toast('success', response.message)
      setLastTemporaryPassword(response.temporary_password)
      replaceUser(response.user)
      setStats(await getAdminStats())
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
    setVideoHours(user.video_duration_limit_s === null ? '' : String(user.video_duration_limit_s / 3600))
    setMakeAdmin(user.is_admin)
    setActivateAccount(user.is_active)
    setCreateIfMissing(false)
    setFullName(user.full_name || '')
    setInitialPassword('')
    setLastTemporaryPassword(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function toggleActive(user: AdminUser) {
    try {
      const updated = user.is_active ? await deactivateUser(user.id) : await activateUser(user.id)
      replaceUser(updated)
      setStats(await getAdminStats())
      toast('success', updated.is_active ? 'Compte réactivé' : 'Compte bloqué')
    } catch (err: any) {
      toast('error', err?.response?.data?.detail || 'Action impossible')
    }
  }

  async function removeUser(user: AdminUser) {
    if (!confirm(`Supprimer définitivement le compte ${user.email} ? Cette action supprime aussi ses vidéos/jobs.`)) return
    try {
      await deleteUser(user.id)
      setUsers((prev) => prev.filter((u) => u.id !== user.id))
      setStats(await getAdminStats())
      toast('success', 'Compte supprimé')
    } catch (err: any) {
      toast('error', err?.response?.data?.detail || 'Suppression impossible')
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-8">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-primary-500/15 flex items-center justify-center">
            <Shield className="w-6 h-6 text-primary-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Administration CutForge</h1>
            <p className="text-dark-400 mt-1">Utilisateurs, abonnements, accès illimité, blocage et supervision plateforme.</p>
          </div>
        </div>
        <button onClick={() => loadAll(q)} className="btn-secondary flex items-center justify-center gap-2">
          <RefreshCw className="w-4 h-4" /> Rafraîchir
        </button>
      </div>

      {stats && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard label="Utilisateurs" value={stats.users_total} icon={Users} />
          <StatCard label="Enterprise illimité" value={stats.enterprise_users} icon={Crown} />
          <StatCard label="Montages/jobs" value={stats.jobs_total} icon={Video} />
          <StatCard label="Revenus validés" value={formatMoney(stats.revenue_xof)} icon={CheckCircle} />
          <StatCard label="Comptes actifs" value={stats.active_users} icon={CheckCircle} />
          <StatCard label="Comptes bloqués" value={stats.blocked_users} icon={Ban} />
          <StatCard label="Jobs en cours" value={stats.processing_jobs + stats.pending_jobs} icon={Loader2} />
          <StatCard label="Jobs échoués" value={stats.failed_jobs} icon={AlertTriangle} />
        </div>
      )}

      <form onSubmit={submitGrant} className="card mb-8 grid gap-5 lg:grid-cols-[1.5fr_1fr_1fr]">
        <div className="lg:col-span-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Attribuer / modifier un accès</h2>
            <p className="text-sm text-dark-400 mt-1">Enterprise + durée illimitée = montages illimités.</p>
          </div>
          {currentUser?.is_admin && <span className="text-xs px-3 py-1 rounded-full bg-primary-500/15 text-primary-200">Connecté admin</span>}
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-2">Email du client</label>
          <input className="input w-full" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="client@email.com" required />
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Nom complet</label>
          <input className="input w-full" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Nom du client" />
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Mot de passe initial</label>
          <input className="input w-full" value={initialPassword} onChange={(e) => setInitialPassword(e.target.value)} placeholder="Vide = généré auto" type="text" />
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
          <label className="block text-sm text-dark-300 mb-2">Durée de l’accès</label>
          <select className="input w-full" value={duration} onChange={(e) => setDuration(e.target.value)}>
            {quickDurations.map((d) => <option key={d.label} value={d.value}>{d.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm text-dark-300 mb-2">Maximum par vidéo (heures)</label>
          <input
            className="input w-full"
            type="number"
            min="0"
            max="168"
            step="0.25"
            value={videoHours}
            onChange={(e) => setVideoHours(e.target.value)}
            placeholder="Vide = règle du plan"
          />
          <p className="text-xs text-dark-500 mt-1">0 = durée illimitée · 1,5 = 1 h 30</p>
        </div>

        <div className="lg:col-span-3 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
          <div className="flex flex-wrap gap-4 text-sm text-dark-300">
            <label className="flex items-center gap-2"><input type="checkbox" checked={createIfMissing} onChange={(e) => setCreateIfMissing(e.target.checked)} /> Créer si absent</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={activateAccount} onChange={(e) => setActivateAccount(e.target.checked)} /> Compte actif</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={makeAdmin} onChange={(e) => setMakeAdmin(e.target.checked)} /> Accès administrateur</label>
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
            <span className="ml-2 text-amber-200/80">À afficher une seule fois puis à faire changer.</span>
          </div>
        )}
      </form>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between mb-4">
        <h2 className="text-xl font-semibold">Tous les comptes</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); loadAll(q) }}>
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
            <div key={user.id} className="card hover:border-primary-500/50 transition-colors">
              <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
                <button onClick={() => fillUser(user)} className="text-left flex-1">
                  <div className="font-semibold flex flex-wrap items-center gap-2">
                    {user.email}
                    {user.is_super_admin && <span className="text-xs px-2 py-1 rounded-full bg-amber-500/15 text-amber-200">FONDATEUR</span>}
                    {user.is_admin && !user.is_super_admin && <span className="text-xs px-2 py-1 rounded-full bg-primary-500/15 text-primary-300">ADMIN</span>}
                    {!user.is_active && <span className="text-xs px-2 py-1 rounded-full bg-red-500/15 text-red-300">BLOQUÉ</span>}
                  </div>
                  <div className="text-sm text-dark-500 mt-1">
                    {user.full_name || 'Sans nom'} · {user.videos_count} vidéo(s) · {user.jobs_count} job(s) · {formatMoney(user.total_spent_xof)}
                  </div>
                </button>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="flex items-center gap-1 text-accent-300"><Crown className="w-4 h-4" /> {planLabel(user)}</span>
                  <span className="flex items-center gap-1 text-primary-200"><Video className="w-4 h-4" /> {videoLimitLabel(user)}</span>
                  <span className="flex items-center gap-1 text-dark-300"><Calendar className="w-4 h-4" /> {formatExpiry(user.subscription_expires_at)}</span>
                  <span className={user.is_active ? 'text-emerald-400 flex items-center gap-1' : 'text-red-400 flex items-center gap-1'}>
                    {user.is_active ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    {user.is_active ? 'Actif' : 'Bloqué'}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => fillUser(user)} className="btn-secondary text-sm py-2 px-3">Modifier</button>
                  <button onClick={() => toggleActive(user)} className="btn-secondary text-sm py-2 px-3 flex items-center gap-1">
                    {user.is_active ? <Ban className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
                    {user.is_active ? 'Bloquer' : 'Réactiver'}
                  </button>
                  <button onClick={() => removeUser(user)} className="text-red-300 hover:text-red-200 border border-red-500/30 rounded-xl px-3 py-2 flex items-center gap-1">
                    <Trash2 className="w-4 h-4" /> Supprimer
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
