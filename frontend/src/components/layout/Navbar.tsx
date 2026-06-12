import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { LogOut, User, Shield } from 'lucide-react'
import Logo from '../ui/Logo'
import { BRAND } from '../../brand'

export default function Navbar() {
  const { accessToken, user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <nav className="border-b border-dark-800 bg-dark-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo size={32} />
            <span className="text-xl font-bold font-display tracking-tight">
              Cut<span className="gradient-text">Forge</span>
            </span>
          </Link>

          <div className="flex items-center gap-4">
            <Link to="/pricing" className="text-dark-300 hover:text-white transition-colors">
              Tarifs
            </Link>

            {accessToken ? (
              <>
                <Link to="/dashboard" className="text-dark-300 hover:text-white transition-colors">
                  Dashboard
                </Link>
                {user?.is_admin && (
                  <Link to="/admin" className="text-dark-300 hover:text-white transition-colors flex items-center gap-1">
                    <Shield className="w-4 h-4" />
                    Admin
                  </Link>
                )}
                <div className="flex items-center gap-3">
                  <span className="text-sm text-dark-400 hidden sm:flex items-center gap-1">
                    <User className="w-4 h-4" />
                    {user?.email || 'Compte'}
                  </span>
                  <button onClick={handleLogout} className="text-dark-400 hover:text-white transition-colors" aria-label="Se déconnecter">
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
        </div>
      </div>
    </nav>
  )
}
