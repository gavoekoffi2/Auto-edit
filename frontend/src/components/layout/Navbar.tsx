import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { Zap, LogOut, User } from 'lucide-react'

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
          <Link to="/" className="flex items-center gap-2">
            <Zap className="w-8 h-8 text-accent-500" />
            <span className="text-xl font-bold gradient-text">AutoEdit</span>
          </Link>

          <div className="flex items-center gap-4">
            <Link to="/pricing" className="text-dark-300 hover:text-white transition-colors">
              Pricing
            </Link>

            {accessToken ? (
              <>
                <Link to="/dashboard" className="text-dark-300 hover:text-white transition-colors">
                  Dashboard
                </Link>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-dark-400 flex items-center gap-1">
                    <User className="w-4 h-4" />
                    {user?.email || 'Account'}
                  </span>
                  <button onClick={handleLogout} className="text-dark-400 hover:text-white transition-colors" aria-label="Log out">
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary text-sm py-2 px-4">
                  Log In
                </Link>
                <Link to="/signup" className="btn-primary text-sm py-2 px-4">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
