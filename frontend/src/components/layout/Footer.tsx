import { Zap } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="border-t border-dark-800 bg-dark-950 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <Zap className="w-6 h-6 text-accent-500" />
            <span className="text-lg font-bold gradient-text">AutoEdit</span>
          </div>
          <p className="text-dark-500 text-sm">
            &copy; {new Date().getFullYear()} AutoEdit. AI-powered video editing.
          </p>
        </div>
      </div>
    </footer>
  )
}
