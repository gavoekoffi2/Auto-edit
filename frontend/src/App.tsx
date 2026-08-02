import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import AppShell from './components/layout/AppShell'
import Navbar from './components/layout/Navbar'
import ErrorBoundary from './components/ui/ErrorBoundary'
import PageTransition from './components/ui/PageTransition'
import ToastContainer from './components/ui/Toast'
import { getMe } from './api/auth'

// Lazy-loaded pages for code splitting
const Landing = lazy(() => import('./pages/Landing'))
const Login = lazy(() => import('./pages/Login'))
const Signup = lazy(() => import('./pages/Signup'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const Editor = lazy(() => import('./pages/Editor'))
const Clips = lazy(() => import('./pages/Clips'))
const Pricing = lazy(() => import('./pages/Pricing'))
const NotFound = lazy(() => import('./pages/NotFound'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))

/**
 * Attente de chargement d'un écran.
 *
 * Un spinner centré sur fond vide fait « page cassée » une fraction de
 * seconde. Trois barres qui pulsent occupent la place du contenu à venir:
 * l'œil comprend qu'il attend, pas que ça a échoué.
 */
function PageLoader() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 px-4 py-12" aria-busy>
      <div className="skeleton h-9 w-56" />
      <div className="skeleton h-4 w-80" />
      <div className="skeleton h-64 w-full" />
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

/**
 * Choisit la coquille selon l'état de session.
 *
 * Le parcours connecté n'a rien à faire sous la barre du site vitrine: il a
 * sa propre structure (rail, en-tête, onglets mobiles). `/pricing` bascule
 * d'une coquille à l'autre selon qu'on est connecté — c'est la même page,
 * mais on ne « sort » plus du produit pour aller payer.
 */
function Shell({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken)
  const location = useLocation()
  const body = <PageTransition key={location.pathname}>{children}</PageTransition>

  if (!token) {
    return (
      <>
        <Navbar />
        {body}
      </>
    )
  }
  return <AppShell>{body}</AppShell>
}

export default function App() {
  const token = useAuthStore((s) => s.accessToken)
  const setUser = useAuthStore((s) => s.setUser)

  useEffect(() => {
    if (token) {
      getMe().then(setUser).catch(() => {})
    }
  }, [token, setUser])

  return (
    <ErrorBoundary>
      <div className="min-h-screen">
        <ToastContainer />
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* --- vitrine: barre publique, quelle que soit la session --- */}
            <Route path="/" element={<><Navbar /><Landing /></>} />
            <Route path="/login" element={<><Navbar /><Login /></>} />
            <Route path="/signup" element={<><Navbar /><Signup /></>} />
            <Route path="/forgot-password" element={<><Navbar /><ForgotPassword /></>} />

            {/* --- pages qui suivent la session --- */}
            <Route path="/pricing" element={<Shell><Pricing /></Shell>} />

            {/* --- parcours connecté --- */}
            <Route
              path="/dashboard"
              element={<ProtectedRoute><Shell><Dashboard /></Shell></ProtectedRoute>}
            />
            <Route
              path="/admin"
              element={<ProtectedRoute><Shell><AdminDashboard /></Shell></ProtectedRoute>}
            />
            <Route
              path="/editor/:videoId"
              element={<ProtectedRoute><Shell><Editor /></Shell></ProtectedRoute>}
            />
            <Route
              path="/clips"
              element={<ProtectedRoute><Shell><Clips /></Shell></ProtectedRoute>}
            />

            <Route path="*" element={<><Navbar /><NotFound /></>} />
          </Routes>
        </Suspense>
      </div>
    </ErrorBoundary>
  )
}
