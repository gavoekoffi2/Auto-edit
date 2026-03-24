import { Link } from 'react-router-dom'
import { Zap, Wand2, Clock, Globe, Mic, Scissors, Sparkles, Film } from 'lucide-react'
import Footer from '../components/layout/Footer'

const features = [
  {
    icon: Mic,
    title: 'AI Transcription',
    description: 'Automatic speech-to-text powered by Whisper AI. Generate subtitles instantly.',
  },
  {
    icon: Clock,
    title: 'Silence Removal',
    description: 'Automatically detect and remove dead air, pauses, and silence from your videos.',
  },
  {
    icon: Scissors,
    title: 'Smart Scene Detection',
    description: 'AI detects scene changes and intelligently cuts your video into perfect segments.',
  },
  {
    icon: Sparkles,
    title: 'Auto Effects',
    description: 'Add transitions, zoom effects, and dynamic visuals with a single click.',
  },
  {
    icon: Film,
    title: 'Multi-Format Export',
    description: 'Export optimized for TikTok, YouTube, or Podcast with preset configurations.',
  },
  {
    icon: Globe,
    title: 'Cloud Processing',
    description: 'Upload once, process in the cloud. No heavy software needed.',
  },
]

const modes = [
  {
    name: 'TikTok Mode',
    emoji: '🔥',
    description: 'Vertical crop, fast cuts, auto-subtitles, 60s max',
    color: 'from-rose-500 to-pink-500',
  },
  {
    name: 'YouTube Mode',
    emoji: '🎥',
    description: 'Optimized for engagement, silence removal, chapters',
    color: 'from-red-500 to-orange-500',
  },
  {
    name: 'Podcast Mode',
    emoji: '🎙️',
    description: 'Audio cleanup, silence removal, auto-transcription',
    color: 'from-purple-500 to-indigo-500',
  },
]

export default function Landing() {
  return (
    <div>
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-900/20 via-dark-950 to-accent-900/20" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-32">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 bg-primary-500/10 border border-primary-500/20 rounded-full px-4 py-1.5 mb-8">
              <Zap className="w-4 h-4 text-accent-400" />
              <span className="text-sm text-primary-300">AI-Powered Video Editing</span>
            </div>

            <h1 className="text-5xl md:text-7xl font-bold mb-6">
              Edit Videos
              <span className="gradient-text"> Automatically</span>
              <br />with AI
            </h1>

            <p className="text-xl text-dark-400 mb-10 max-w-2xl mx-auto">
              Upload your video, choose a mode, and let AutoEdit handle the rest.
              Silence removal, scene detection, subtitles, and effects — all automated.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/signup" className="btn-primary text-lg py-3 px-8 flex items-center gap-2">
                <Zap className="w-5 h-5" />
                Start Editing Free
              </Link>
              <Link to="/pricing" className="btn-secondary text-lg py-3 px-8">
                View Pricing
              </Link>
            </div>

            {/* Demo visualization */}
            <div className="mt-16 relative">
              <div className="bg-dark-900 border border-dark-700 rounded-2xl p-8 shadow-2xl">
                <div className="flex items-center gap-4 mb-6">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-500" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500" />
                    <div className="w-3 h-3 rounded-full bg-green-500" />
                  </div>
                  <span className="text-dark-500 text-sm">AutoEdit Dashboard</span>
                </div>

                <div className="bg-dark-800 rounded-xl aspect-video flex items-center justify-center">
                  <div className="text-center">
                    <Wand2 className="w-16 h-16 text-primary-500 mx-auto mb-4" />
                    <p className="text-lg font-medium text-dark-300">Upload → AI Process → Export</p>
                    <p className="text-dark-500 mt-2">Your video, perfected in minutes</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 border-t border-dark-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Everything You Need to
              <span className="gradient-text"> AutoEdit</span>
            </h2>
            <p className="text-dark-400 text-lg max-w-2xl mx-auto">
              Powered by cutting-edge open-source AI tools: Whisper, auto-editor, PySceneDetect, and MoviePy.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <div key={feature.title} className="card hover:border-dark-600 transition-colors group">
                <feature.icon className="w-10 h-10 text-primary-500 mb-4 group-hover:text-accent-400 transition-colors" />
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-dark-400">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modes */}
      <section className="py-24 border-t border-dark-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Smart Editing
              <span className="gradient-text"> Modes</span>
            </h2>
            <p className="text-dark-400 text-lg">One click. Perfect output for every platform.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {modes.map((mode) => (
              <div key={mode.name} className="card hover:border-dark-600 transition-all group text-center">
                <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${mode.color} flex items-center justify-center mx-auto mb-4 text-3xl`}>
                  {mode.emoji}
                </div>
                <h3 className="text-xl font-semibold mb-2">{mode.name}</h3>
                <p className="text-dark-400">{mode.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pipeline */}
      <section className="py-24 border-t border-dark-800 bg-dark-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              How It
              <span className="gradient-text"> Works</span>
            </h2>
          </div>

          <div className="flex flex-col md:flex-row items-center justify-center gap-4">
            {['Upload', 'AI Analysis', 'Remove Silence', 'Detect Scenes', 'Apply Effects', 'Add Subtitles', 'Export'].map(
              (step, i) => (
                <div key={step} className="flex items-center gap-4">
                  <div className="flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-primary-400 font-bold">
                      {i + 1}
                    </div>
                    <span className="text-sm text-dark-400 mt-2 whitespace-nowrap">{step}</span>
                  </div>
                  {i < 6 && (
                    <div className="hidden md:block w-8 h-0.5 bg-dark-700" />
                  )}
                </div>
              )
            )}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 border-t border-dark-800">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            Ready to AutoEdit?
          </h2>
          <p className="text-dark-400 text-lg mb-8">
            Start editing your videos with AI today. No credit card required.
          </p>
          <Link to="/signup" className="btn-primary text-lg py-3 px-8 inline-flex items-center gap-2">
            <Zap className="w-5 h-5" />
            Get Started Free
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  )
}
