import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ChevronDown, CreditCard, Crown, LayoutGrid, LogOut, Scissors, Shield,
  Sparkles, User,
} from 'lucide-react'
import Logo from '../ui/Logo'
import { useAuthStore } from '../../store/authStore'
import { BRAND } from '../../brand'

interface NavEntry {
  to: string
  label: string
  icon: typeof LayoutGrid
  admin?: boolean
}

const NAV: NavEntry[] = [
  { to: '/dashboard', label: 'Studio', icon: LayoutGrid },
  { to: '/clips', label: 'Clips', icon: Scissors },
  { to: '/pricing', label: 'Abonnement', icon: CreditCard },
  { to: '/admin', label: 'Admin', icon: Shield, admin: true },
]

/**
 * Coquille de l'application CONNECTÉE.
 *
 * Avant, les écrans connectés vivaient sous la même barre que le site vitrine:
 * une rangée de liens texte, aucun repère de section, rien sur mobile hormis
 * des liens tassés. Un outil a besoin d'une structure permanente — c'est elle
 * qui donne le sentiment d'être « dans » un produit et pas sur une page.
 *
 *   * desktop  — rail latéral fixe, section active soulignée d'un indicateur
 *                qui GLISSE d'un item à l'autre (`layoutId`);
 *   * mobile   — barre d'onglets basse, à portée de pouce, la même hiérarchie;
 *   * partout  — en-tête collante avec le fil d'ariane et le menu de compte.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const entries = NAV.filter((entry) => !entry.admin || user?.is_admin)
  const plan = (user?.effective_plan || user?.plan || 'free').toLowerCase()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="relative min-h-screen">
      {/* Ambiance: deux halos très diffus, fixes. Ils donnent une profondeur de
          champ à toute l'application sans jamais bouger sous le contenu. */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
        <div className="halo left-[-12%] top-[-18%] h-[520px] w-[520px] bg-primary-700/25" />
        <div className="halo right-[-10%] top-[6%] h-[420px] w-[420px] bg-iris-700/20" />
        <div className="absolute inset-0 cf-grid-dots opacity-40" />
      </div>

      {/* ---------------- rail latéral (desktop) ---------------- */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col border-r border-white/[0.06] bg-surface-base/80 px-4 py-5 backdrop-blur-xl lg:flex">
        <Link to="/dashboard" className="flex items-center gap-2.5 px-2">
          <Logo size={30} />
          <span className="font-display text-lg font-bold tracking-tight">
            Cut<span className="gradient-text">Forge</span>
          </span>
        </Link>

        <nav className="mt-8 flex flex-col gap-1">
          <p className="eyebrow px-3 pb-2">Espace de travail</p>
          {entries.map((entry) => (
            <SideLink key={entry.to} entry={entry} active={isActive(location.pathname, entry.to)} />
          ))}
        </nav>

        <div className="mt-auto space-y-3">
          <PlanCard plan={plan} />
          <p className="px-2 text-[11px] leading-relaxed text-dark-600">{BRAND.tagline}</p>
        </div>
      </aside>

      {/* ---------------- en-tête collante ---------------- */}
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-surface-canvas/72 backdrop-blur-xl lg:pl-[248px]">
        <div className="flex h-16 items-center gap-3 shell-gutter">
          <Link to="/dashboard" className="flex items-center gap-2 lg:hidden">
            <Logo size={26} />
            <span className="font-display text-base font-bold tracking-tight">CutForge</span>
          </Link>

          <p className="hidden min-w-0 flex-1 items-center gap-2 text-sm text-dark-400 lg:flex">
            <span className="truncate font-medium text-dark-200">
              {sectionTitle(location.pathname)}
            </span>
          </p>

          <div className="ml-auto flex items-center gap-2">
            <span
              className={`hidden items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-bold tracking-wider sm:inline-flex ${
                plan === 'free'
                  ? 'border border-white/10 bg-white/[0.04] text-dark-400'
                  : 'border border-amber-300/35 bg-amber-300/10 text-amber-300'
              }`}
            >
              {plan !== 'free' && <Crown className="h-3 w-3" />}
              {plan.toUpperCase()}
            </span>
            <AccountMenu email={user?.email} onLogout={handleLogout} />
          </div>
        </div>
      </header>

      {/* ---------------- contenu ---------------- */}
      <main className="pb-28 lg:pb-16 lg:pl-[248px]">{children}</main>

      {/* ---------------- onglets (mobile) ---------------- */}
      <nav
        // Opacité volontairement haute: un fond translucide laissait le
        // contenu défiler VISIBLEMENT derrière les onglets, ce qui rendait les
        // libellés illisibles dès qu'une carte claire passait dessous.
        className="fixed inset-x-0 bottom-0 z-40 border-t border-white/[0.07] bg-[#08080d]/97 pb-[env(safe-area-inset-bottom)] backdrop-blur-2xl lg:hidden"
        aria-label="Navigation principale"
      >
        <div className="flex items-stretch">
          {entries.map((entry) => {
            const active = isActive(location.pathname, entry.to)
            return (
              <NavLink
                key={entry.to}
                to={entry.to}
                className="relative flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-semibold"
              >
                {active && (
                  <motion.span
                    layoutId="tab-indicator"
                    className="absolute inset-x-4 top-0 h-[2px] rounded-full bg-brand-sweep"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
                <entry.icon className={`h-[18px] w-[18px] ${active ? 'text-primary-300' : 'text-dark-500'}`} />
                <span className={active ? 'text-white' : 'text-dark-500'}>{entry.label}</span>
              </NavLink>
            )
          })}
        </div>
      </nav>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
function SideLink({ entry, active }: { entry: NavEntry; active: boolean }) {
  const Icon = entry.icon
  return (
    <NavLink to={entry.to} className="nav-item" data-active={active}>
      {active && (
        <motion.span
          layoutId="rail-indicator"
          className="absolute inset-0 -z-10 rounded-xl border border-white/[0.08] bg-white/[0.06]"
          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
        />
      )}
      {active && (
        <motion.span
          layoutId="rail-bar"
          className="absolute -left-4 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-sweep"
          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
        />
      )}
      <Icon className="nav-icon h-[18px] w-[18px]" />
      {entry.label}
    </NavLink>
  )
}

/* -------------------------------------------------------------------------- */
function PlanCard({ plan }: { plan: string }) {
  if (plan !== 'free') {
    return (
      <div className="rounded-xl border border-amber-300/25 bg-amber-300/[0.07] p-3">
        <p className="flex items-center gap-1.5 text-xs font-bold text-amber-300">
          <Crown className="h-3.5 w-3.5" /> PLAN {plan.toUpperCase()}
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-dark-400">
          Rendus prioritaires et quotas étendus actifs.
        </p>
      </div>
    )
  }
  return (
    <Link
      to="/pricing"
      className="group block overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-br from-primary-600/18 via-iris-600/12 to-transparent p-3 transition-colors hover:border-primary-500/40"
    >
      <p className="flex items-center gap-1.5 text-xs font-bold text-white">
        <Sparkles className="h-3.5 w-3.5 text-primary-300" /> Passer en Pro
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-dark-400">
        Vidéos plus longues, rendus prioritaires, sans filigrane.
      </p>
    </Link>
  )
}

/* -------------------------------------------------------------------------- */
function AccountMenu({ email, onLogout }: { email?: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Un menu qui ne se ferme ni au clic extérieur ni à Échap est un piège: sur
  // mobile il masque le contenu et l'utilisateur croit l'application bloquée.
  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const initial = (email || '?').trim().charAt(0).toUpperCase()

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] py-1 pl-1 pr-2.5 transition-colors hover:border-white/20"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-sweep text-xs font-bold text-white">
          {initial}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 text-dark-400 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="glass-panel absolute right-0 top-11 w-60 overflow-hidden rounded-2xl p-1.5"
          >
            <div className="flex items-center gap-2.5 px-2.5 py-2">
              <User className="h-4 w-4 shrink-0 text-dark-500" />
              <span className="min-w-0 truncate text-xs text-dark-300">{email || 'Compte'}</span>
            </div>
            <div className="my-1 h-px bg-white/[0.07]" />
            <Link
              to="/pricing"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-medium text-dark-300 transition-colors hover:bg-white/[0.06] hover:text-white"
            >
              <CreditCard className="h-4 w-4" /> Abonnement et factures
            </Link>
            <button
              role="menuitem"
              onClick={onLogout}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-medium text-dark-300 transition-colors hover:bg-red-500/10 hover:text-red-300"
            >
              <LogOut className="h-4 w-4" /> Se déconnecter
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
function isActive(pathname: string, to: string) {
  if (to === '/dashboard') return pathname === '/dashboard' || pathname.startsWith('/editor')
  return pathname.startsWith(to)
}

function sectionTitle(pathname: string) {
  if (pathname.startsWith('/editor')) return 'Studio · Montage'
  if (pathname.startsWith('/clips')) return 'Clips'
  if (pathname.startsWith('/pricing')) return 'Abonnement'
  if (pathname.startsWith('/admin')) return 'Administration'
  return 'Studio'
}
