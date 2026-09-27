import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { LogOut, User, Shield } from 'lucide-react'
import { logoutApi } from '../../api/auth'
import Logo from '../ui/Logo'
import { BRAND } from '../../brand'

export default function Navbar() {
  const { accessToken, user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    // Révoque le refresh token côté serveur AVANT de l'oublier localement.
    await logoutApi()
    logout()
    navigate('/')
  }

  return (
    <nav className="border-b border-dark-800 bg-dark-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo size={32} />
            <span className="hidden sm:inline text-xl font-bold font-display tracking-tight">
              Cut<span className="gradient-text">Forge</span>
            </span>
          </Link>

          <div className="flex items-center gap-3 sm:gap-4 text-sm sm:text-base">
            <Link to="/pricing" className="text-dark-300 hover:text-white transition-colors">
              Tarifs
            </Link>

            {accessToken ? (
              <>
                <Link to="/dashboard" className="text-dark-300 hover:text-white transition-colors">
                  Dashboard
                </Link>
                <Link to="/clips" className="text-dark-300 hover:text-white transition-colors">
                  Clips
                </Link>
                <Link to="/pub" className="text-dark-300 hover:text-white transition-colors">
                  Pub IA
                </Link>
                {user?.is_admin && (
                  <Link to="/admin" className="text-dark-300 hover:text-white transition-colors flex items-center gap-1">
                    <Shield className="w-4 h-4" />
                    <span className="hidden sm:inline">Admin</span>
                  </Link>
                )}
                <div className="flex items-center gap-3">
                  <Link
                    to="/account"
                    className="text-sm text-dark-400 hover:text-white transition-colors flex items-center gap-1"
                    aria-label="Mon compte"
                  >
                    <User className="w-4 h-4" />
                    <span className="hidden md:inline max-w-[180px] truncate">{user?.email || 'Compte'}</span>
                  </Link>
                  <button onClick={handleLogout} className="text-dark-400 hover:text-white transition-colors" aria-label="Se déconnecter">
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary text-sm py-2 px-3 sm:px-4">
                  Connexion
                </Link>
                <Link to="/signup" className="btn-primary text-sm py-2 px-3 sm:px-4">
                  Commencer
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
