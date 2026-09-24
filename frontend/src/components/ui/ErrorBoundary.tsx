import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
    // Après un déploiement, un onglet resté ouvert réclame d'anciens fichiers
    // JS qui n'existent plus: on recharge la page UNE fois pour récupérer la
    // nouvelle version au lieu d'afficher une erreur.
    const isChunkError = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i
      .test(error?.message || '')
    if (isChunkError) {
      try {
        if (!sessionStorage.getItem('cf_chunk_reload')) {
          sessionStorage.setItem('cf_chunk_reload', '1')
          window.location.reload()
        }
      } catch {
        /* stockage indisponible: on affiche l'écran d'erreur */
      }
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[60vh] flex items-center justify-center px-4">
          <div className="card max-w-md text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold mb-2">Oups, un problème est survenu</h2>
            <p className="text-dark-400 mb-4 text-sm">
              Recharge la page. Si le problème persiste, contacte le support.
            </p>
            <div className="flex gap-3 justify-center">
              <button onClick={this.handleReset} className="btn-secondary flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Réessayer
              </button>
              <button onClick={() => window.location.href = '/'} className="btn-primary">
                Accueil
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
