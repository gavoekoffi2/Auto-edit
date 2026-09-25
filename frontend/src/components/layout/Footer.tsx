import { Link } from 'react-router-dom'
import Logo from '../ui/Logo'
import { BRAND } from '../../brand'

export default function Footer() {
  return (
    <footer className="border-t border-dark-800 bg-dark-950 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex flex-col items-center md:items-start gap-2">
            <div className="flex items-center gap-2.5">
              <Logo size={26} />
              <span className="text-lg font-bold font-display tracking-tight">
                Cut<span className="gradient-text">Forge</span>
              </span>
            </div>
            <p className="text-dark-500 text-sm">{BRAND.tagline}</p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-dark-400">
            <Link to="/pricing" className="hover:text-white transition-colors">Tarifs</Link>
            <Link to="/terms" className="hover:text-white transition-colors">CGU</Link>
            <Link to="/privacy" className="hover:text-white transition-colors">Confidentialité</Link>
            <a href={`mailto:${BRAND.supportEmail}`} className="hover:text-white transition-colors">Support</a>
          </div>
          <p className="text-dark-500 text-sm">
            &copy; {new Date().getFullYear()} {BRAND.name}. Montage vidéo propulsé par l'IA.
          </p>
        </div>
      </div>
    </footer>
  )
}
