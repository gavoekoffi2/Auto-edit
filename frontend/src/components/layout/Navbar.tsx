import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { LogOut, User, Shield, Menu, X } from 'lucide-react'
import { logoutApi } from '../../api/auth'
import Logo from '../ui/Logo'
import { BRAND } from '../../brand'

export default function Navbar() {
  const { accessToken, user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const handleLogout = async () => {
    setMenuOpen(false)
    // Révoque le refresh token côté serveur AVANT de l'oublier localement.
    await logoutApi()
    logout()
    navigate('/')
  }

  // Le menu se referme à chaque navigation: sans ça, cliquer un lien laissait
  // le panneau ouvert par-dessus la page qu'on venait d'ouvrir.
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  // Échap ferme le menu, et le corps de page ne défile plus derrière lui.
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    const onPointerDown = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onPointerDown)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onPointerDown)
      document.body.style.overflow = previous
    }
  }, [menuOpen])

  const navLinkClass = 'text-dark-300 hover:text-white transition-colors'
  const mobileLinkClass =
    'block w-full rounded-lg px-4 py-3 text-base text-dark-200 hover:bg-dark-800 hover:text-white transition-colors'

  return (
    <nav className="border-b border-dark-800 bg-dark-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2.5" aria-label={BRAND.name}>
            <Logo size={32} />
            <span className="text-xl font-bold font-display tracking-tight">
              Cut<span className="gradient-text">Forge</span>
            </span>
          </Link>

          {/* Desktop — au-delà de lg (plus de liens depuis Studio, Shorts, Pub IA), tous les liens tiennent sur une ligne. */}
          <div className="hidden lg:flex items-center gap-4">
            <Link to="/pricing" className={navLinkClass}>
              Tarifs
            </Link>

            {accessToken ? (
              <>
                <Link to="/dashboard" className={navLinkClass}>
                  Dashboard
                </Link>
                <Link to="/studio" className="relative font-semibold text-white transition-colors hover:text-primary-200">
                  Studio
                  <span className="absolute -right-2 -top-1.5 h-1.5 w-1.5 rounded-full bg-accent-400 shadow-[0_0_10px_rgba(251,146,60,.9)]" />
                </Link>
                <Link to="/shorts" className={`whitespace-nowrap ${navLinkClass}`}>
                  Shorts
                </Link>
                <Link to="/clips" className={navLinkClass}>
                  Clips
                </Link>
                <Link to="/pub" className={`whitespace-nowrap ${navLinkClass}`}>
                  Pub IA
                </Link>
                {user?.is_admin && (
                  <Link to="/admin" className={`${navLinkClass} flex items-center gap-1`}>
                    <Shield className="w-4 h-4" />
                    Admin
                  </Link>
                )}
                <div className="flex items-center gap-3">
                  <Link
                    to="/account"
                    className="text-sm text-dark-400 hover:text-white transition-colors flex items-center gap-1"
                    aria-label="Mon compte"
                  >
                    <User className="w-4 h-4" />
                    <span className="max-w-[180px] truncate">{user?.email || 'Compte'}</span>
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="text-dark-400 hover:text-white transition-colors"
                    aria-label="Se déconnecter"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary text-sm py-2 px-4">
                  Connexion
                </Link>
                <Link to="/signup" className="btn-primary text-sm py-2 px-4">
                  Commencer
                </Link>
              </>
            )}
          </div>

          {/* Mobile — le burger. En dessous de lg, la barre de liens débordait
              hors de l'écran: l'e-mail du compte poussait « Connexion » et
              « Commencer » hors cadre, et les liens devenaient intouchables. */}
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="lg:hidden inline-flex items-center justify-center rounded-lg p-2 text-dark-200 hover:text-white hover:bg-dark-800 transition-colors"
            aria-label={menuOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
          >
            {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <div
          id="mobile-menu"
          ref={panelRef}
          className="lg:hidden border-t border-dark-800 bg-dark-950/95 backdrop-blur-sm"
        >
          <div className="max-w-7xl mx-auto px-4 py-3 space-y-1">
            {accessToken && (
              <div className="flex items-center gap-2 px-4 pb-2 text-sm text-dark-400 break-all">
                <User className="w-4 h-4 shrink-0" />
                {user?.email || 'Compte'}
              </div>
            )}

            <Link to="/pricing" className={mobileLinkClass}>
              Tarifs
            </Link>

            {accessToken ? (
              <>
                <Link to="/dashboard" className={mobileLinkClass}>
                  Dashboard
                </Link>
                <Link to="/studio" className={`${mobileLinkClass} font-semibold text-white`}>
                  Studio
                </Link>
                <Link to="/shorts" className={mobileLinkClass}>
                  Shorts
                </Link>
                <Link to="/clips" className={mobileLinkClass}>
                  Clips
                </Link>
                <Link to="/pub" className={mobileLinkClass}>
                  Pub IA
                </Link>
                <Link to="/account" className={`${mobileLinkClass} flex items-center gap-2`}>
                  <User className="w-4 h-4" />
                  Mon compte
                </Link>
                {user?.is_admin && (
                  <Link to="/admin" className={`${mobileLinkClass} flex items-center gap-2`}>
                    <Shield className="w-4 h-4" />
                    Admin
                  </Link>
                )}
                <button
                  onClick={handleLogout}
                  className={`${mobileLinkClass} flex items-center gap-2 text-left`}
                >
                  <LogOut className="w-4 h-4" />
                  Se déconnecter
                </button>
              </>
            ) : (
              <div className="flex flex-col gap-2 pt-2">
                <Link to="/login" className="btn-secondary text-center text-sm py-2.5">
                  Connexion
                </Link>
                <Link to="/signup" className="btn-primary text-center text-sm py-2.5">
                  Commencer
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </nav>
  )
}
