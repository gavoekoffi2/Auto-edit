import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { LogOut, User, Shield, Menu, X } from 'lucide-react'
import Logo from '../ui/Logo'
import { BRAND } from '../../brand'

export default function Navbar() {
  const { accessToken, user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const handleLogout = () => {
    setMenuOpen(false)
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

          {/* Desktop — au-delà de md, tous les liens tiennent sur une ligne. */}
          <div className="hidden md:flex items-center gap-4">
            <Link to="/pricing" className={navLinkClass}>
              Tarifs
            </Link>

            {accessToken ? (
              <>
                <Link to="/dashboard" className={navLinkClass}>
                  Dashboard
                </Link>
                <Link to="/clips" className={navLinkClass}>
                  Clips
                </Link>
                {user?.is_admin && (
                  <Link to="/admin" className={`${navLinkClass} flex items-center gap-1`}>
                    <Shield className="w-4 h-4" />
                    Admin
                  </Link>
                )}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-dark-400 flex items-center gap-1">
                    <User className="w-4 h-4" />
                    {user?.email || 'Compte'}
                  </span>
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

          {/* Mobile — le burger. En dessous de md, la barre de liens débordait
              hors de l'écran: l'e-mail du compte poussait « Connexion » et
              « Commencer » hors cadre, et les liens devenaient intouchables. */}
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="md:hidden inline-flex items-center justify-center rounded-lg p-2 text-dark-200 hover:text-white hover:bg-dark-800 transition-colors"
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
          className="md:hidden border-t border-dark-800 bg-dark-950/95 backdrop-blur-sm"
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
                <Link to="/clips" className={mobileLinkClass}>
                  Clips
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
