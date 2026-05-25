import { Link } from 'react-router-dom'
import { useRef, useState } from 'react'
import {
  motion,
  useScroll,
  useTransform,
  useReducedMotion,
  AnimatePresence,
  type Variants,
} from 'framer-motion'
import {
  ArrowRight,
  Sparkles,
  Wand2,
  Clock,
  Subtitles,
  Image as ImageIcon,
  Music,
  Scissors,
  Smartphone,
  Play,
  Check,
  ChevronDown,
  Star,
  Zap,
  ShieldCheck,
} from 'lucide-react'
import Footer from '../components/layout/Footer'

// ============================================================================
// Photos hébergées sur Unsplash — créateurs et entrepreneurs en environnement
// urbain moderne. Les URLs sont stables (CDN Unsplash).
// ============================================================================
const PORTRAITS = {
  aisha:
    'https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=320&q=80',
  kossi:
    'https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=320&q=80',
  fatima:
    'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=320&q=80',
  yannick:
    'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=320&q=80',
  awa:
    'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=320&q=80',
}

const HERO_VIDEO_THUMB =
  'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?auto=format&fit=crop&w=1280&q=80'

const SHOWCASE_IMAGES = [
  'https://images.unsplash.com/photo-1573164574572-cb89e39749b4?auto=format&fit=crop&w=640&q=80',
  'https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=640&q=80',
  'https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=640&q=80',
  'https://images.unsplash.com/photo-1543269865-cbf427effbad?auto=format&fit=crop&w=640&q=80',
]

// ============================================================================
// Helpers de motion
// ============================================================================
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 28 },
  show: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.65, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] },
  }),
}

const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}

// ============================================================================
// Composant principal
// ============================================================================
export default function Landing() {
  return (
    <main className="overflow-x-clip">
      <Hero />
      <SocialProof />
      <Pain />
      <Solution />
      <Features />
      <HowItWorks />
      <Modes />
      <Showcase />
      <Stats />
      <Testimonials />
      <PricingTeaser />
      <Faq />
      <FinalCta />
      <Footer />
    </main>
  )
}

// ============================================================================
// HERO
// ============================================================================
function Hero() {
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const y1 = useTransform(scrollYProgress, [0, 1], [0, -120])
  const y2 = useTransform(scrollYProgress, [0, 1], [0, 80])
  const opacity = useTransform(scrollYProgress, [0, 0.6], [1, 0.4])

  return (
    <section
      ref={ref}
      className="relative pt-20 sm:pt-28 pb-24 overflow-hidden noise"
      style={{
        backgroundImage:
          'radial-gradient(ellipse 90% 50% at 50% -10%, rgba(63,114,255,0.18), transparent 60%), radial-gradient(ellipse 80% 50% at 90% 20%, rgba(249,115,22,0.12), transparent 60%), radial-gradient(ellipse 60% 50% at 10% 30%, rgba(168,85,247,0.14), transparent 60%)',
      }}
    >
      {/* Grid background */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.15] bg-grid-fade bg-grid-32"
        style={{ maskImage: 'linear-gradient(to bottom, black 30%, transparent 95%)' }}
      />

      {/* Floating blobs */}
      {!reduce && (
        <>
          <motion.div
            style={{ y: y1 }}
            className="pointer-events-none absolute -top-32 -left-20 w-[520px] h-[520px] rounded-full bg-primary-600/20 blur-[120px] animate-float-slow"
          />
          <motion.div
            style={{ y: y2 }}
            className="pointer-events-none absolute top-20 right-0 w-[460px] h-[460px] rounded-full bg-accent-500/20 blur-[120px] animate-float-slower"
          />
        </>
      )}

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="show"
          className="text-center max-w-4xl mx-auto"
        >
          {/* Badge */}
          <motion.div
            variants={fadeUp}
            custom={0}
            className="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 mb-7 text-sm"
          >
            <span className="relative flex w-2 h-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-accent-400 opacity-70 animate-ping" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-500" />
            </span>
            <span className="text-white/80">Nouveau · Pipeline IA V2 disponible</span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            variants={fadeUp}
            custom={1}
            className="text-balance text-[40px] leading-[1.05] sm:text-6xl md:text-7xl font-bold tracking-tight"
          >
            Tu enregistres.{' '}
            <span className="gradient-text animate-gradient-x">L&apos;IA monte.</span>
            <br className="hidden sm:block" />
            Tu publies.
          </motion.h1>

          {/* Sub */}
          <motion.p
            variants={fadeUp}
            custom={2}
            className="text-balance text-lg sm:text-xl text-white/70 mt-6 max-w-2xl mx-auto leading-relaxed"
          >
            Charge ta vidéo brute. AutoEdit coupe les silences, ajoute des
            sous-titres dynamiques, du B-roll, de la musique et un habillage
            premium. <span className="text-white">5&nbsp;minutes</span> au lieu
            de 4&nbsp;heures.
          </motion.p>

          {/* CTAs */}
          <motion.div
            variants={fadeUp}
            custom={3}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3"
          >
            <Link
              to="/signup"
              className="group relative overflow-hidden btn-primary text-base py-3.5 px-7 inline-flex items-center gap-2 shadow-glow-primary"
            >
              <span className="relative z-10 flex items-center gap-2">
                Lancer mon premier montage
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </span>
              <span
                aria-hidden
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent translate-x-[-150%] group-hover:translate-x-[150%] transition-transform duration-700"
              />
            </Link>
            <Link
              to="/pricing"
              className="btn-secondary text-base py-3.5 px-7 inline-flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Voir une démo
            </Link>
          </motion.div>

          {/* Trust line */}
          <motion.div
            variants={fadeUp}
            custom={4}
            className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-white/50"
          >
            <span className="inline-flex items-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-400" /> 2 vidéos gratuites
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-400" /> Sans carte bancaire
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-400" /> Paiement Mobile Money
            </span>
          </motion.div>
        </motion.div>

        {/* Mockup */}
        <motion.div
          style={{ opacity }}
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="relative mt-16 sm:mt-20 max-w-5xl mx-auto"
        >
          <HeroMockup />
        </motion.div>
      </div>
    </section>
  )
}

function HeroMockup() {
  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute -inset-x-8 -bottom-10 h-40 bg-gradient-to-t from-dark-950 to-transparent"
      />
      <div className="glass rounded-2xl overflow-hidden shadow-card-premium">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <div className="flex-1 text-center text-xs text-white/40">
            autoedit.app — Studio
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
          {/* Preview */}
          <div className="md:col-span-2 relative aspect-video bg-dark-900">
            <img
              src={HERO_VIDEO_THUMB}
              alt="Aperçu studio AutoEdit"
              className="absolute inset-0 w-full h-full object-cover opacity-90"
              loading="eager"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            {/* Play */}
            <button
              type="button"
              className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-white/95 text-dark-900 flex items-center justify-center shadow-2xl"
              aria-label="Lire la démo"
            >
              <Play className="w-6 h-6 fill-current" />
            </button>
            {/* Subtitle overlay */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.1, duration: 0.6 }}
              className="absolute bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-md bg-black/70 backdrop-blur border border-white/10 text-sm font-semibold tracking-wide"
            >
              <span className="text-accent-300">Lance</span> ton business
              aujourd&apos;hui
            </motion.div>
            {/* Timeline */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/10">
              <motion.div
                initial={{ width: '12%' }}
                animate={{ width: '64%' }}
                transition={{ duration: 2.4, ease: 'easeInOut', repeat: Infinity, repeatType: 'reverse' }}
                className="h-full bg-gradient-to-r from-primary-500 to-accent-500"
              />
            </div>
          </div>

          {/* Side panel */}
          <div className="p-5 bg-dark-900/60 border-t md:border-t-0 md:border-l border-white/5 space-y-4">
            <SideStep done label="Transcription" sub="Mot par mot" />
            <SideStep done label="Coupes intelligentes" sub="Silences + filler words" />
            <SideStep done label="B-roll IA" sub="Contextuel" />
            <SideStep active label="Sous-titres dynamiques" sub="En cours…" />
            <SideStep label="Export 1080p · 9:16" />
          </div>
        </div>
      </div>
    </div>
  )
}

function SideStep(props: { label: string; sub?: string; done?: boolean; active?: boolean }) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
          props.done
            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
            : props.active
            ? 'bg-primary-500/20 text-primary-300 border border-primary-500/40 animate-pulse-soft'
            : 'bg-white/5 text-white/30 border border-white/10'
        }`}
      >
        {props.done ? <Check className="w-3 h-3" /> : props.active ? '…' : ''}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">{props.label}</p>
        {props.sub && <p className="text-xs text-white/50">{props.sub}</p>}
      </div>
    </div>
  )
}

// ============================================================================
// SOCIAL PROOF — bandeau plateformes + créateurs
// ============================================================================
function SocialProof() {
  const items = [
    'TikTok', 'Instagram Reels', 'YouTube Shorts', 'WhatsApp Business',
    'Facebook', 'LinkedIn', 'Snapchat', 'Pinterest',
  ]
  return (
    <section className="py-10 border-y border-white/5 bg-dark-900/40">
      <p className="text-center text-xs uppercase tracking-[0.2em] text-white/40 mb-5">
        Optimisé pour les plateformes où ton audience scrolle
      </p>
      <div className="mask-fade-x overflow-hidden">
        <motion.div
          className="flex gap-12 whitespace-nowrap"
          animate={{ x: ['0%', '-50%'] }}
          transition={{ duration: 38, repeat: Infinity, ease: 'linear' }}
        >
          {[...items, ...items, ...items].map((p, i) => (
            <span
              key={i}
              className="text-xl sm:text-2xl font-display font-semibold text-white/30 hover:text-white/60 transition-colors"
            >
              {p}
            </span>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// PAIN — Le vrai problème
// ============================================================================
function Pain() {
  const pains = [
    {
      stat: '4h',
      title: 'pour monter 1 minute',
      desc: "Tu passes plus de temps à monter qu'à créer. Capcut, Premiere, DaVinci — chaque outil exige une courbe d&apos;apprentissage.",
      tone: 'red',
    },
    {
      stat: '3s',
      title: 'avant que ton viewer scrolle',
      desc: "Un montage lent, c'est une audience perdue. Les algorithmes punissent les vidéos qui n'accrochent pas dès la première seconde.",
      tone: 'orange',
    },
    {
      stat: '50K',
      title: 'FCFA pour un monteur',
      desc: "Externaliser, c'est cher, lent, et tu perds le contrôle créatif. Multiplie par 10 vidéos par mois — le budget explose.",
      tone: 'amber',
    },
  ]

  return (
    <section className="py-24 sm:py-32 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-80px' }}
          variants={stagger}
          className="max-w-3xl mx-auto text-center mb-16"
        >
          <motion.p
            variants={fadeUp}
            className="text-sm uppercase tracking-[0.2em] text-accent-400 font-semibold mb-4"
          >
            Le vrai problème
          </motion.p>
          <motion.h2
            variants={fadeUp}
            custom={1}
            className="text-balance text-3xl sm:text-5xl font-bold leading-tight"
          >
            Tu as <span className="text-accent-300">le talent</span>.
            <br />
            Le montage te le vole.
          </motion.h2>
          <motion.p
            variants={fadeUp}
            custom={2}
            className="text-white/60 text-lg mt-6 leading-relaxed"
          >
            Chaque jour qui passe sans publier, c'est une audience qui choisit
            quelqu'un d'autre. Le problème n'est pas ton contenu — c'est tout
            ce qui se passe entre l'enregistrement et la publication.
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-50px' }}
          variants={stagger}
          className="grid md:grid-cols-3 gap-5"
        >
          {pains.map((p, i) => (
            <motion.div
              key={p.title}
              variants={fadeUp}
              custom={i}
              whileHover={{ y: -4 }}
              className="relative card overflow-hidden group"
            >
              <div
                aria-hidden
                className={`absolute -top-16 -right-16 w-48 h-48 rounded-full blur-3xl opacity-30 group-hover:opacity-50 transition ${
                  p.tone === 'red'
                    ? 'bg-red-500'
                    : p.tone === 'orange'
                    ? 'bg-accent-500'
                    : 'bg-amber-500'
                }`}
              />
              <div className="relative">
                <p className="text-5xl font-display font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-br from-white to-white/40">
                  {p.stat}
                </p>
                <h3 className="text-lg font-semibold mb-3">{p.title}</h3>
                <p className="text-white/60 leading-relaxed">{p.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// SOLUTION — Avant / Après
// ============================================================================
function Solution() {
  return (
    <section className="py-24 sm:py-32 relative border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="max-w-3xl mx-auto text-center mb-16"
        >
          <motion.p
            variants={fadeUp}
            className="text-sm uppercase tracking-[0.2em] text-primary-300 font-semibold mb-4"
          >
            La solution
          </motion.p>
          <motion.h2 variants={fadeUp} custom={1} className="text-3xl sm:text-5xl font-bold leading-tight">
            Une <span className="gradient-text">IA qui monte à ta place</span>,
            pas un éditeur que tu dois apprendre.
          </motion.h2>
          <motion.p variants={fadeUp} custom={2} className="text-white/60 text-lg mt-6">
            AutoEdit comprend ce que tu dis, coupe ce qui n'apporte rien,
            illustre tes idées et habille ta vidéo. Tu valides, tu publies.
          </motion.p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-6 lg:gap-10 items-stretch">
          <BeforeAfter
            label="Sans AutoEdit"
            tone="bad"
            duration="03:47"
            metrics={[
              { label: 'Temps de montage', value: '4h 12min' },
              { label: 'Filler words', value: '38 « euh »' },
              { label: 'Silences morts', value: '6 min cumulées' },
              { label: 'Sous-titres', value: 'À taper à la main' },
            ]}
          />
          <BeforeAfter
            label="Avec AutoEdit"
            tone="good"
            duration="00:58"
            metrics={[
              { label: 'Temps de montage', value: '4 min 32s' },
              { label: 'Filler words', value: '0 (auto)' },
              { label: 'Silences morts', value: '0 (auto)' },
              { label: 'Sous-titres', value: 'Animés, dynamiques' },
            ]}
          />
        </div>
      </div>
    </section>
  )
}

function BeforeAfter(props: {
  label: string
  tone: 'good' | 'bad'
  duration: string
  metrics: { label: string; value: string }[]
}) {
  const good = props.tone === 'good'
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className={`relative card overflow-hidden ${
        good ? 'border-emerald-500/30 shadow-glow-primary' : 'border-white/10'
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <span
          className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
            good
              ? 'bg-emerald-500/15 text-emerald-300'
              : 'bg-red-500/15 text-red-300'
          }`}
        >
          {props.label}
        </span>
        <span className="text-white/40 text-sm font-mono">{props.duration}</span>
      </div>

      <div className={`relative aspect-video rounded-lg overflow-hidden mb-5 ${good ? 'ring-1 ring-emerald-500/30' : ''}`}>
        <div
          className={`absolute inset-0 ${
            good
              ? 'bg-gradient-to-br from-emerald-500/20 via-primary-500/10 to-transparent'
              : 'bg-gradient-to-br from-red-500/10 via-dark-800 to-dark-800'
          }`}
        />
        {/* "Waveform" */}
        <div className="absolute inset-x-4 top-1/2 -translate-y-1/2 flex items-end gap-[3px] h-16">
          {Array.from({ length: 48 }).map((_, i) => {
            const seed = (i * 37) % 100
            const h = good
              ? 30 + (seed % 60)
              : seed < 15
              ? 4
              : seed < 60
              ? 8 + (seed % 30)
              : 12
            return (
              <div
                key={i}
                style={{ height: `${h}%` }}
                className={`w-[3px] rounded-full ${
                  good ? 'bg-emerald-300' : 'bg-white/30'
                }`}
              />
            )
          })}
        </div>
        {good && (
          <motion.div
            initial={{ x: '-100%' }}
            whileInView={{ x: '110%' }}
            viewport={{ once: true }}
            transition={{ duration: 2.2, ease: 'easeInOut', delay: 0.3 }}
            className="absolute inset-y-0 w-1 bg-white/70 shadow-[0_0_20px_rgba(255,255,255,0.8)]"
          />
        )}
      </div>

      <dl className="space-y-2.5 text-sm">
        {props.metrics.map((m) => (
          <div key={m.label} className="flex items-center justify-between">
            <dt className="text-white/50">{m.label}</dt>
            <dd
              className={`font-semibold ${
                good ? 'text-emerald-300' : 'text-white/80'
              }`}
            >
              {m.value}
            </dd>
          </div>
        ))}
      </dl>
    </motion.div>
  )
}

// ============================================================================
// FEATURES
// ============================================================================
function Features() {
  const features = [
    {
      icon: Scissors,
      title: 'Coupes intelligentes',
      desc: "Silences morts, hésitations, faux départs : tout disparaît automatiquement, sans coupures brutales.",
    },
    {
      icon: Subtitles,
      title: 'Sous-titres dynamiques',
      desc: 'Mot par mot, synchronisés, animés. Lisibles même son coupé — comme les vidéos qui font 10M de vues.',
    },
    {
      icon: ImageIcon,
      title: 'B-roll IA contextuel',
      desc: "L'IA comprend ce que tu racontes et illustre tes propos avec des visuels premium au bon moment.",
    },
    {
      icon: Music,
      title: 'Musique & SFX',
      desc: 'Musique de fond qui baisse quand tu parles, effets sonores synchronisés sur les transitions.',
    },
    {
      icon: Smartphone,
      title: 'Formats verticaux natifs',
      desc: 'Export 9:16 prêt pour TikTok, Reels, Shorts — ou 16:9 pour YouTube, 1:1 pour Instagram.',
    },
    {
      icon: ShieldCheck,
      title: 'Tes vidéos restent à toi',
      desc: 'Aucun entraînement sur tes contenus. Tu peux supprimer ta vidéo à tout moment.',
    },
  ]

  return (
    <section className="py-24 sm:py-32 relative border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="max-w-3xl mx-auto text-center mb-16"
        >
          <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] text-primary-300 font-semibold mb-4">
            Ce que fait AutoEdit
          </motion.p>
          <motion.h2 variants={fadeUp} custom={1} className="text-3xl sm:text-5xl font-bold leading-tight">
            Tout ce qu'un{' '}
            <span className="gradient-text">monteur expérimenté</span> ferait.
            <br />
            Sans le délai. Sans la facture.
          </motion.h2>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-50px' }}
          variants={stagger}
          className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5"
        >
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              variants={fadeUp}
              custom={i}
              whileHover={{ y: -3, transition: { duration: 0.2 } }}
              className="group relative card overflow-hidden"
            >
              <div
                aria-hidden
                className="absolute inset-0 bg-gradient-to-br from-primary-500/0 via-primary-500/0 to-accent-500/0 group-hover:from-primary-500/10 group-hover:to-accent-500/10 transition-all duration-500"
              />
              <div className="relative">
                <div className="inline-flex w-11 h-11 rounded-xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 border border-white/10 items-center justify-center mb-4 group-hover:scale-110 group-hover:rotate-3 transition-transform">
                  <f.icon className="w-5 h-5 text-primary-300" />
                </div>
                <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-white/60 leading-relaxed text-sm">{f.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// HOW IT WORKS — 3 étapes
// ============================================================================
function HowItWorks() {
  const steps = [
    {
      n: '01',
      title: 'Charge ta vidéo',
      desc: 'Glisse-dépose un fichier MP4, MOV ou WebM. Jusqu’à 500 Mo. Aucun logiciel à installer.',
      tag: '< 30 secondes',
    },
    {
      n: '02',
      title: 'Choisis un style',
      desc: 'TikTok viral, Business premium, Publicité locale, Podcast propre, Formation. Active les options.',
      tag: '1 clic',
    },
    {
      n: '03',
      title: 'Récupère ta vidéo',
      desc: "L'IA monte, illustre, sous-titre. Tu télécharges un MP4 prêt à publier sur n'importe quelle plateforme.",
      tag: '~ 5 minutes',
    },
  ]

  return (
    <section className="py-24 sm:py-32 relative border-t border-white/5 bg-dark-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="max-w-3xl mx-auto text-center mb-16"
        >
          <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] text-accent-400 font-semibold mb-4">
            En 3 étapes
          </motion.p>
          <motion.h2 variants={fadeUp} custom={1} className="text-3xl sm:text-5xl font-bold leading-tight">
            Plus simple qu'envoyer un message{' '}
            <span className="gradient-text">WhatsApp</span>.
          </motion.h2>
        </motion.div>

        <div className="relative">
          {/* connector line */}
          <div
            aria-hidden
            className="hidden md:block absolute top-12 left-[12%] right-[12%] h-px bg-gradient-to-r from-transparent via-white/15 to-transparent"
          />
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-50px' }}
            variants={stagger}
            className="grid md:grid-cols-3 gap-6 relative"
          >
            {steps.map((s, i) => (
              <motion.div
                key={s.n}
                variants={fadeUp}
                custom={i}
                className="card relative overflow-hidden"
              >
                <div className="flex items-center justify-between mb-5">
                  <span className="font-display text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-primary-300 to-accent-300">
                    {s.n}
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-white/5 border border-white/10 text-white/60">
                    {s.tag}
                  </span>
                </div>
                <h3 className="text-xl font-semibold mb-2">{s.title}</h3>
                <p className="text-white/60 leading-relaxed">{s.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}

// ============================================================================
// MODES — cartes avec couleur
// ============================================================================
function Modes() {
  const modes = [
    {
      icon: '🔥',
      name: 'TikTok viral',
      desc: 'Captions animées, B-roll, CTA',
      gradient: 'from-rose-500/40 to-orange-500/40',
    },
    {
      icon: '💼',
      name: 'Business premium',
      desc: 'B-roll moderne, musique sobre, CTA pro',
      gradient: 'from-primary-500/40 to-violet-500/40',
    },
    {
      icon: '📣',
      name: 'Publicité locale',
      desc: 'Restaurant, boutique, service — CTA clair',
      gradient: 'from-accent-500/40 to-amber-500/40',
    },
    {
      icon: '🎙️',
      name: 'Podcast propre',
      desc: 'Silences nettoyés, audio préservé',
      gradient: 'from-emerald-500/40 to-teal-500/40',
    },
    {
      icon: '🎓',
      name: 'Formation',
      desc: 'Captions lisibles, B-roll discret, 16:9',
      gradient: 'from-sky-500/40 to-cyan-500/40',
    },
  ]
  return (
    <section className="py-24 sm:py-32 border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="max-w-3xl mx-auto text-center mb-14"
        >
          <motion.h2 variants={fadeUp} className="text-3xl sm:text-5xl font-bold">
            Un style pensé pour <span className="gradient-text">chaque objectif</span>.
          </motion.h2>
          <motion.p variants={fadeUp} custom={1} className="text-white/60 text-lg mt-5">
            Sélectionne, lance, publie. Chaque mode applique les bonnes
            coupes, la bonne mise en page et le bon rythme.
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-50px' }}
          variants={stagger}
          className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4"
        >
          {modes.map((m, i) => (
            <motion.div
              key={m.name}
              variants={fadeUp}
              custom={i}
              whileHover={{ y: -4, scale: 1.02 }}
              transition={{ type: 'spring', stiffness: 250, damping: 18 }}
              className="group relative rounded-2xl p-5 overflow-hidden border border-white/10 bg-dark-900"
            >
              <div
                aria-hidden
                className={`absolute -top-12 -right-10 w-44 h-44 rounded-full blur-3xl bg-gradient-to-br ${m.gradient} opacity-50 group-hover:opacity-100 transition`}
              />
              <div className="relative">
                <div className="text-3xl mb-3">{m.icon}</div>
                <p className="font-semibold">{m.name}</p>
                <p className="text-sm text-white/55 mt-1">{m.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// SHOWCASE — mur d'images avec parallax
// ============================================================================
function Showcase() {
  return (
    <section className="py-24 sm:py-32 border-t border-white/5 relative overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="grid md:grid-cols-12 gap-10 items-center"
        >
          <motion.div variants={fadeUp} className="md:col-span-5">
            <p className="text-sm uppercase tracking-[0.2em] text-primary-300 font-semibold mb-4">
              Pensé pour ton public
            </p>
            <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
              Des visuels qui parlent à{' '}
              <span className="gradient-text">ta communauté</span>.
            </h2>
            <p className="text-white/60 text-lg mt-5 leading-relaxed">
              Le B-roll IA d&apos;AutoEdit génère des scènes qui résonnent avec
              ton audience : créateurs, entrepreneurs, commerçants,
              formateurs. Pas des stocks génériques importés d&apos;ailleurs.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm text-white/70">
              <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> Scènes contextuelles modernes</li>
              <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> Photographie réaliste, jamais cliché</li>
              <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> Style configurable par mode</li>
            </ul>
          </motion.div>

          <motion.div
            variants={fadeUp}
            custom={1}
            className="md:col-span-7 grid grid-cols-2 gap-3 sm:gap-4"
          >
            {SHOWCASE_IMAGES.map((src, i) => (
              <motion.div
                key={src}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                whileHover={{ scale: 1.03 }}
                className={`relative overflow-hidden rounded-xl aspect-[4/5] ${
                  i % 2 === 1 ? 'translate-y-6' : ''
                }`}
              >
                <img
                  src={src}
                  alt=""
                  className="absolute inset-0 w-full h-full object-cover"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// STATS
// ============================================================================
function Stats() {
  const stats = [
    { value: '10x', label: 'plus rapide qu’un montage manuel' },
    { value: '~5 min', label: 'pour une vidéo prête à publier' },
    { value: '0', label: 'logiciel à installer' },
    { value: '5', label: 'styles pré-configurés' },
  ]
  return (
    <section className="py-20 border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="grid grid-cols-2 md:grid-cols-4 gap-6"
        >
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              variants={fadeUp}
              custom={i}
              className="text-center p-6 rounded-2xl border border-white/5 bg-dark-900/40"
            >
              <p className="font-display text-4xl sm:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-white to-white/50">
                {s.value}
              </p>
              <p className="text-white/60 text-sm mt-2 leading-tight">{s.label}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// TESTIMONIALS
// ============================================================================
function Testimonials() {
  const items = [
    {
      quote:
        'Avant AutoEdit je publiais une vidéo TikTok par semaine. Aujourd’hui c’est 5. Mon audience a triplé en deux mois.',
      name: 'Aïsha K.',
      role: 'Créatrice de contenu',
      avatar: PORTRAITS.aisha,
    },
    {
      quote:
        'Je tourne mes plats le matin, AutoEdit monte pendant que je sers le midi. Mes ventes du soir ont augmenté de 40 %.',
      name: 'Kossi A.',
      role: 'Restaurateur',
      avatar: PORTRAITS.kossi,
    },
    {
      quote:
        'J’ai arrêté de payer 50 000 FCFA par vidéo à mon monteur. Et la qualité est meilleure.',
      name: 'Fatima D.',
      role: 'Coach business',
      avatar: PORTRAITS.fatima,
    },
    {
      quote:
        'Mes formations sont enfin regardées jusqu’à la fin. Les sous-titres dynamiques changent tout.',
      name: 'Yannick T.',
      role: 'Formateur en ligne',
      avatar: PORTRAITS.yannick,
    },
    {
      quote:
        'L’IA comprend mon contenu et choisit des visuels qui matchent. Mes Reels font 10x plus de vues.',
      name: 'Awa M.',
      role: 'Influenceuse beauté',
      avatar: PORTRAITS.awa,
    },
  ]
  return (
    <section className="py-24 sm:py-32 border-t border-white/5 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={stagger}
          className="max-w-3xl mx-auto text-center mb-16"
        >
          <motion.p variants={fadeUp} className="text-sm uppercase tracking-[0.2em] text-accent-400 font-semibold mb-4">
            Ils l&apos;utilisent déjà
          </motion.p>
          <motion.h2 variants={fadeUp} custom={1} className="text-3xl sm:text-5xl font-bold leading-tight">
            Des créateurs et entrepreneurs{' '}
            <span className="gradient-text">qui publient plus</span>.
          </motion.h2>
        </motion.div>

        <div className="mask-fade-x overflow-hidden">
          <motion.div
            className="flex gap-5 w-max"
            animate={{ x: ['0%', '-50%'] }}
            transition={{ duration: 50, repeat: Infinity, ease: 'linear' }}
          >
            {[...items, ...items].map((t, i) => (
              <article
                key={i}
                className="w-[320px] sm:w-[380px] shrink-0 card flex flex-col gap-4"
              >
                <div className="flex gap-1 text-accent-400">
                  {Array.from({ length: 5 }).map((_, k) => (
                    <Star key={k} className="w-4 h-4 fill-current" />
                  ))}
                </div>
                <p className="text-white/85 leading-relaxed">{t.quote}</p>
                <div className="flex items-center gap-3 mt-auto pt-4 border-t border-white/5">
                  <img
                    src={t.avatar}
                    alt={t.name}
                    className="w-10 h-10 rounded-full object-cover border border-white/10"
                    loading="lazy"
                  />
                  <div>
                    <p className="font-semibold text-sm">{t.name}</p>
                    <p className="text-xs text-white/50">{t.role}</p>
                  </div>
                </div>
              </article>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}

// ============================================================================
// PRICING TEASER
// ============================================================================
function PricingTeaser() {
  return (
    <section className="py-24 sm:py-32 border-t border-white/5">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 grid md:grid-cols-2 gap-8 items-center">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-primary-300 font-semibold mb-4">
            Tarif
          </p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight">
            Moins cher qu&apos;<span className="gradient-text">une seule vidéo</span> chez un monteur.
          </h2>
          <p className="text-white/60 text-lg mt-5">
            5 000 FCFA / mois. Vidéos illimitées. Tous les styles. Pas
            d&apos;engagement. Annule en un clic depuis ton dashboard.
          </p>
          <Link to="/pricing" className="btn-secondary mt-6 inline-flex items-center gap-2">
            Voir tous les plans <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="relative card shadow-glow-primary border-primary-500/30"
        >
          <div className="absolute -top-3 left-6">
            <span className="bg-accent-500 text-white text-xs font-bold tracking-wider px-3 py-1 rounded-full">
              LE PLUS POPULAIRE
            </span>
          </div>
          <div className="flex items-baseline gap-2 mb-2 mt-2">
            <span className="text-5xl font-display font-bold">5 000</span>
            <span className="text-white/60">FCFA / mois</span>
          </div>
          <p className="text-white/60 mb-5 text-sm">Soit 10 $ — ou ~167 FCFA / jour.</p>
          <ul className="space-y-2.5 text-sm">
            {[
              'Vidéos illimitées · 30 min max',
              'Pipeline IA V2 + B-roll',
              'Tous les styles (TikTok, Business…)',
              'Sous-titres dynamiques',
              'Musique + SFX',
              'Export 1080p 9:16',
              'Support prioritaire',
            ].map((f) => (
              <li key={f} className="flex items-center gap-2 text-white/80">
                <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                {f}
              </li>
            ))}
          </ul>
          <Link
            to="/signup"
            className="btn-primary w-full justify-center mt-6 inline-flex items-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Démarrer mon essai
          </Link>
        </motion.div>
      </div>
    </section>
  )
}

// ============================================================================
// FAQ
// ============================================================================
function Faq() {
  const items = [
    {
      q: 'Quelle est la durée maximale de mes vidéos ?',
      a: 'En plan Free, 5 minutes par vidéo et 2 vidéos par mois. En plan Pro, 30 minutes par vidéo et illimité par mois. En Enterprise, aucune limite.',
    },
    {
      q: 'Combien de temps prend un montage ?',
      a: 'Compte environ 5 minutes pour une vidéo de 1 minute, et 10 à 15 minutes pour une vidéo de 5 minutes. Tu reçois une notification quand c’est prêt.',
    },
    {
      q: 'Quels formats vidéo sont supportés ?',
      a: 'MP4, MOV, WebM, AVI, MKV, FLV, WMV. Taille maximale 500 Mo par fichier. L’export se fait toujours en MP4 H.264 compatible TikTok / Reels / Shorts.',
    },
    {
      q: 'Mes vidéos sont-elles privées ?',
      a: 'Oui. Tes vidéos appartiennent uniquement à toi. Nous ne les utilisons jamais pour entraîner nos modèles. Tu peux les supprimer définitivement à tout moment depuis ton dashboard.',
    },
    {
      q: 'Puis-je payer avec Mobile Money ?',
      a: 'Oui — Orange Money, MTN Mobile Money, Moov Money et Wave sont supportés via FedaPay. Tu peux aussi payer par carte Visa / Mastercard.',
    },
    {
      q: 'Puis-je annuler à tout moment ?',
      a: 'Oui. Aucun engagement. Annule en un clic depuis ton dashboard. L’abonnement reste actif jusqu’à la fin du mois payé.',
    },
  ]
  return (
    <section className="py-24 sm:py-32 border-t border-white/5">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <p className="text-sm uppercase tracking-[0.2em] text-primary-300 font-semibold mb-4">
            FAQ
          </p>
          <h2 className="text-3xl sm:text-5xl font-bold leading-tight">
            Les questions qu&apos;on{' '}
            <span className="gradient-text">se pose toujours</span>.
          </h2>
        </motion.div>

        <div className="space-y-3">
          {items.map((it, i) => (
            <FaqItem key={i} q={it.q} a={it.a} />
          ))}
        </div>
      </div>
    </section>
  )
}

function FaqItem(props: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.45 }}
      className="card overflow-hidden p-0"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between text-left px-5 py-4 gap-4"
        aria-expanded={open}
      >
        <span className="font-medium">{props.q}</span>
        <ChevronDown
          className={`w-5 h-5 text-white/50 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 text-white/70 leading-relaxed text-sm">
              {props.a}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ============================================================================
// FINAL CTA
// ============================================================================
function FinalCta() {
  return (
    <section className="relative py-28 sm:py-36 border-t border-white/5 overflow-hidden">
      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 60% 60% at 50% 50%, rgba(63,114,255,0.25), transparent 70%), radial-gradient(ellipse 80% 60% at 30% 30%, rgba(249,115,22,0.18), transparent 60%)',
        }}
      />
      <div className="relative max-w-3xl mx-auto px-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
        >
          <Sparkles className="w-10 h-10 text-accent-300 mx-auto mb-5" />
          <h2 className="text-4xl sm:text-6xl font-bold leading-tight">
            Ta prochaine vidéo virale est{' '}
            <span className="gradient-text">à 5 minutes</span>.
          </h2>
          <p className="text-white/65 text-lg mt-6 max-w-xl mx-auto">
            Tes concurrents publient pendant que tu montes. Reprends ton temps.
          </p>
          <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to="/signup"
              className="btn-primary text-base py-3.5 px-7 inline-flex items-center gap-2 shadow-glow-primary"
            >
              <Wand2 className="w-4 h-4" />
              Lancer mon premier montage
            </Link>
            <Link to="/pricing" className="btn-secondary text-base py-3.5 px-7">
              Voir les tarifs
            </Link>
          </div>
          <p className="text-white/40 text-xs mt-5 inline-flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            Inscription en 30 secondes · 2 vidéos gratuites · Sans carte
          </p>
        </motion.div>
      </div>
    </section>
  )
}
