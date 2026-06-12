import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, Check, ChevronDown, Image as ImageIcon, PenTool, Scissors,
  Smartphone, Sparkles, Subtitles, Upload, Volume2, Wand2, Zap,
} from 'lucide-react'
import Logo from '../components/ui/Logo'
import Footer from '../components/layout/Footer'
import Reveal from '../components/ui/Reveal'
import BeforeAfter from '../components/landing/BeforeAfter'
import { BRAND } from '../brand'
import '../styles/landing.css'

/* ========================================================================== */
/*  Helpers d'animation                                                       */
/* ========================================================================== */

const CYCLE = 12 // secondes — boucle de la simulation de montage du hero

/** Cale une animation partagée sur un instant précis du cycle de 12 s
 *  (delay négatif = déphasage : le keyframe 0% tombe à `startSeconds`). */
function ph(name: string, startSeconds: number): React.CSSProperties {
  return {
    animationName: name,
    animationDelay: `${(startSeconds - CYCLE).toFixed(2)}s`,
    animationTimingFunction: 'linear',
  }
}

/* ========================================================================== */
/*  Simulation de montage — le téléphone du hero                              */
/*  Reproduit en CSS ce que le moteur fait vraiment : captions karaoké,       */
/*  popup mot-clé, B-roll avec flash photo, scène motion design (dessin       */
/*  qui se trace + compteur + cercle marqueur + flèche), pastilles SFX.       */
/* ========================================================================== */

const CAPTION_CHUNKS = [
  ['VOICI', 'LA', 'MÉTHODE'],
  ['POUR', 'EXPLOSER', 'TES'],
  ['VENTES', 'EN', 'LIGNE'],
  ['AVEC', 'CUTFORGE', '🔥'],
]

function useDemoCounter(target = 80, windowStart = 7.35, windowDur = 1.35) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setValue(target)
      return
    }
    let raf = 0
    const tick = () => {
      const t = (performance.now() / 1000) % CYCLE
      const p = Math.min(1, Math.max(0, (t - windowStart) / windowDur))
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, windowStart, windowDur])
  return value
}

function SfxPill({ label, at, side = 'left' }: { label: string; at: number; side?: 'left' | 'right' }) {
  return (
    <span
      className={`pd-cycle absolute ${side === 'left' ? 'left-2' : 'right-2'} top-1/3 z-30 rounded-full bg-black/70 border border-white/15 px-2 py-0.5 text-[9px] font-semibold tracking-wider text-cyan-200 opacity-0`}
      style={ph('pdSfx', at)}
    >
      {label}
    </span>
  )
}

function PhoneDemo() {
  const counter = useDemoCounter()
  return (
    <div className="relative mx-auto w-[270px] sm:w-[300px]">
      {/* halo */}
      <div className="absolute -inset-8 rounded-[3rem] bg-gradient-to-tr from-primary-600/30 via-fuchsia-500/20 to-accent-500/30 blur-2xl" aria-hidden />

      {/* cadre téléphone */}
      <div className="relative rounded-[2.4rem] border border-white/15 bg-dark-900 p-2 shadow-2xl shadow-primary-900/40">
        <div className="absolute left-1/2 top-4 z-40 h-1.5 w-16 -translate-x-1/2 rounded-full bg-black/70" aria-hidden />
        <div className="relative aspect-[9/16] overflow-hidden rounded-[1.9rem] bg-dark-950">

          {/* ----- couche 1 : le speaker (Ken Burns) -------------------- */}
          <div
            className="pd-cycle absolute inset-0"
            style={{ animationName: 'pdKenBurns', animationTimingFunction: 'ease-in-out' }}
          >
            <div className="absolute inset-0 bg-gradient-to-b from-[#1d2440] via-[#232b52] to-[#101326]" />
            {/* silhouette du créateur */}
            <svg viewBox="0 0 100 178" className="absolute inset-x-0 bottom-0 mx-auto h-[72%]" aria-hidden>
              <ellipse cx="50" cy="58" rx="20" ry="22" fill="#5a4634" />
              <path d="M14 178 Q16 112 50 108 Q84 112 86 178 Z" fill="#2a55f5" />
              <path d="M40 96 q10 10 20 0 l0 14 q-10 8 -20 0 Z" fill="#5a4634" />
            </svg>
            {/* barres audio */}
            <div className="absolute bottom-[30%] left-1/2 flex -translate-x-1/2 items-end gap-1" aria-hidden>
              {[0, 1, 2, 3, 4].map((i) => (
                <span
                  key={i}
                  className="pd-bar w-1 rounded bg-cyan-300/80"
                  style={{ height: `${10 + (i % 3) * 7}px`, animationDelay: `${i * 0.13}s` }}
                />
              ))}
            </div>
          </div>

          {/* ----- popup mot-clé ----------------------------------------- */}
          <div
            className="pd-cycle absolute left-1/2 top-[16%] z-20 -translate-x-1/2 rounded-full border-2 border-amber-300 bg-black/70 px-3 py-1 text-[11px] font-extrabold tracking-wider text-white opacity-0"
            style={ph('pdWindow22', 1.2)}
          >
            MOBILE&nbsp;MONEY
          </div>

          {/* ----- B-roll IA --------------------------------------------- */}
          <div className="pd-cycle absolute inset-0 z-20 opacity-0" style={{ animationName: 'pdBroll', animationTimingFunction: 'ease-in-out' }}>
            <div className="absolute inset-0 bg-gradient-to-br from-[#7c4a1e] via-[#a8632a] to-[#2c1c10]" />
            <svg viewBox="0 0 100 178" className="absolute inset-0 h-full w-full" aria-hidden>
              <circle cx="36" cy="64" r="13" fill="#3b2a18" />
              <rect x="20" y="80" width="32" height="42" rx="8" fill="#0e7490" />
              <rect x="56" y="70" width="28" height="44" rx="4" fill="#134e4a" />
              <rect x="60" y="76" width="20" height="12" rx="2" fill="#5eead4" opacity="0.85" />
              <rect x="60" y="92" width="20" height="3" rx="1.5" fill="#99f6e4" opacity="0.6" />
              <rect x="60" y="98" width="14" height="3" rx="1.5" fill="#99f6e4" opacity="0.4" />
            </svg>
            {/* coins cyan façon viseur */}
            <div className="absolute inset-3" aria-hidden>
              <span className="absolute left-0 top-0 h-5 w-5 border-l-2 border-t-2 border-cyan-300" />
              <span className="absolute right-0 top-0 h-5 w-5 border-r-2 border-t-2 border-cyan-300" />
              <span className="absolute bottom-0 left-0 h-5 w-5 border-b-2 border-l-2 border-cyan-300" />
              <span className="absolute bottom-0 right-0 h-5 w-5 border-b-2 border-r-2 border-cyan-300" />
            </div>
            <span className="absolute left-1/2 top-[10%] -translate-x-1/2 rounded-full bg-amber-400 px-2.5 py-0.5 text-[10px] font-extrabold text-black">
              VENDEUR EN LIGNE
            </span>
          </div>

          {/* ----- scène MOTION DESIGN ----------------------------------- */}
          <div className="pd-cycle absolute inset-0 z-20 opacity-0" style={{ animationName: 'pdMotion', animationTimingFunction: 'ease-in-out' }}>
            <div className="absolute inset-0 bg-gradient-to-b from-[#0b0e1a] to-[#1a132e]" />
            <div className="cf-grid-dots absolute inset-0 opacity-60" />

            <span
              className="pd-cycle absolute left-1/2 top-[9%] -translate-x-1/2 rounded-full border border-amber-300 bg-black/60 px-2.5 py-0.5 text-[9px] font-bold tracking-widest text-amber-300 opacity-0"
              style={ph('pdPop', 7.0)}
            >
              CHIFFRE CLÉ
            </span>

            {/* dessin : panier qui se trace trait par trait */}
            <svg viewBox="0 0 100 100" className="absolute left-1/2 top-[20%] h-[34%] w-[60%] -translate-x-1/2" fill="none" aria-hidden>
              <path
                d="M12 26 h14 l10 36 h40 l10 -28 h-52" stroke="#7dd3fc" strokeWidth="4"
                strokeLinecap="round" strokeLinejoin="round" pathLength={100}
                strokeDasharray={100} className="pd-cycle" style={ph('pdDraw', 6.9)}
              />
              <circle cx="42" cy="74" r="5" stroke="#7dd3fc" strokeWidth="4" pathLength={100}
                strokeDasharray={100} className="pd-cycle" style={ph('pdDraw', 7.4)} />
              <circle cx="66" cy="74" r="5" stroke="#7dd3fc" strokeWidth="4" pathLength={100}
                strokeDasharray={100} className="pd-cycle" style={ph('pdDraw', 7.55)} />
            </svg>

            {/* compteur animé (synchronisé au cycle via rAF) */}
            <div className="pd-cycle absolute left-1/2 top-[56%] -translate-x-1/2 text-center opacity-0" style={ph('pdPop', 7.3)}>
              <span className="font-display text-5xl font-bold text-amber-300 drop-shadow-[0_2px_0_rgba(0,0,0,0.7)]">
                {counter}%
              </span>
            </div>

            {/* mot-clé entouré au marqueur */}
            <div className="pd-cycle absolute left-1/2 top-[70%] -translate-x-1/2 opacity-0" style={ph('pdPop', 7.6)}>
              <span className="relative font-display text-2xl font-bold tracking-wide text-white">
                CLIENTS
                <svg viewBox="0 0 120 46" className="absolute -inset-x-4 -inset-y-2 h-[calc(100%+16px)] w-[calc(100%+32px)]" fill="none" aria-hidden>
                  <ellipse
                    cx="60" cy="23" rx="55" ry="19" stroke="#22d3ee" strokeWidth="3"
                    pathLength={100} strokeDasharray={100}
                    className="pd-cycle" style={ph('pdDraw', 7.9)}
                  />
                </svg>
              </span>
            </div>

            {/* flèche dessinée à la main */}
            <svg viewBox="0 0 60 90" className="absolute bottom-[16%] left-[6%] h-[26%]" fill="none" aria-hidden>
              <path
                d="M8 84 Q2 40 34 22 M22 22 L36 20 L34 34" stroke="#fbbf24" strokeWidth="4"
                strokeLinecap="round" pathLength={100} strokeDasharray={100}
                className="pd-cycle" style={ph('pdDraw', 8.1)}
              />
            </svg>
          </div>

          {/* ----- flashs + balayages de transition ----------------------- */}
          <div className="pd-cycle pointer-events-none absolute inset-0 z-30 bg-white opacity-0" style={ph('pdFlash', 3.25)} />
          <div className="pd-cycle pointer-events-none absolute inset-0 z-30 bg-white opacity-0" style={ph('pdFlash', 6.7)} />
          <div className="pointer-events-none absolute inset-0 z-30 overflow-hidden" aria-hidden>
            <div className="pd-cycle absolute -inset-y-10 w-1/3 bg-gradient-to-r from-transparent via-white/70 to-transparent opacity-0" style={ph('pdSweep', 3.25)} />
            <div className="pd-cycle absolute -inset-y-10 w-1/3 bg-gradient-to-r from-transparent via-white/60 to-transparent opacity-0" style={ph('pdSweep', 6.7)} />
          </div>

          {/* ----- pastilles SFX ------------------------------------------ */}
          <SfxPill label="📸 FLASH" at={3.35} side="right" />
          <SfxPill label="〰 RISER" at={6.25} side="left" />
          <SfxPill label="💥 WHOOSH" at={6.8} side="right" />
          <SfxPill label="● POP" at={7.7} side="left" />
          <SfxPill label="♪ DING" at={8.45} side="right" />

          {/* ----- sous-titres karaoké ------------------------------------ */}
          <div className="absolute inset-x-0 bottom-[9%] z-40 flex justify-center">
            {CAPTION_CHUNKS.map((words, k) => (
              <div
                key={k}
                className="pd-cycle absolute flex gap-1.5 font-display text-[17px] font-bold tracking-wide opacity-0"
                style={ph('pdChunk', k * 3)}
              >
                {words.map((w, i) => (
                  <span
                    key={i}
                    className="pd-cycle inline-block text-white drop-shadow-[0_2px_0_rgba(0,0,0,0.85)]"
                    style={ph('pdWord', k * 3 + 0.18 + i * 0.85)}
                  >
                    {w}
                  </span>
                ))}
              </div>
            ))}
          </div>

          {/* ----- barre de progression du montage ------------------------ */}
          <div className="absolute inset-x-6 bottom-3 z-40 h-0.5 overflow-hidden rounded bg-white/15">
            <div className="pd-cycle h-full origin-left bg-gradient-to-r from-primary-400 to-accent-400" style={{ animationName: 'pdProgress' }} />
          </div>
        </div>
      </div>

      {/* chips décoratives flottantes */}
      <div className="cf-float absolute -left-16 top-12 hidden rounded-xl border border-white/10 bg-dark-900/90 px-3 py-2 text-xs font-semibold text-cyan-200 shadow-xl sm:block" style={{ animationDelay: '0.6s' }}>
        ✂️ 38 silences coupés
      </div>
      <div className="cf-float absolute -right-14 top-1/3 hidden rounded-xl border border-white/10 bg-dark-900/90 px-3 py-2 text-xs font-semibold text-amber-200 shadow-xl sm:block">
        🎨 4 scènes motion design
      </div>
      <div className="cf-float absolute -left-12 bottom-16 hidden rounded-xl border border-white/10 bg-dark-900/90 px-3 py-2 text-xs font-semibold text-emerald-200 shadow-xl sm:block" style={{ animationDelay: '1.2s' }}>
        🔊 27 effets sonores pro
      </div>
    </div>
  )
}

/* ========================================================================== */
/*  Vitrines mini-scènes motion design                                        */
/* ========================================================================== */

function MiniFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="ms-float">
      <div className="relative mx-auto aspect-[9/14] w-full max-w-[230px] overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-[#0b0e1a] to-[#191230] shadow-xl">
        <div className="cf-grid-dots absolute inset-0 opacity-50" />
        {children}
      </div>
      <p className="mt-4 text-center text-sm font-semibold text-dark-200">{title}</p>
    </div>
  )
}

function SceneIdea() {
  return (
    <MiniFrame title="Scène « idée » — dessin + mot-clé entouré">
      <svg viewBox="0 0 100 100" className="absolute left-1/2 top-[14%] h-[42%] w-[64%] -translate-x-1/2" fill="none" aria-hidden>
        <path d="M50 12 a23 23 0 0 1 12 42 l0 10 h-24 l0 -10 a23 23 0 0 1 12 -42 Z"
          stroke="#fff" strokeWidth="4" strokeLinejoin="round" pathLength={100}
          strokeDasharray={100} className="ms-cycle" style={{ animationName: 'msDraw' }} />
        <path d="M42 74 h16 M45 81 h10" stroke="#22d3ee" strokeWidth="4" strokeLinecap="round"
          pathLength={100} strokeDasharray={100} className="ms-cycle"
          style={{ animationName: 'msDraw', animationDelay: '0.5s' }} />
      </svg>
      <div className="ms-cycle absolute left-1/2 top-[64%] -translate-x-1/2 opacity-0" style={{ animationName: 'msPop', animationDelay: '0.8s' }}>
        <span className="relative font-display text-xl font-bold text-white">
          LE&nbsp;SECRET
          <svg viewBox="0 0 120 40" className="absolute -inset-x-3 -inset-y-1.5 h-[calc(100%+12px)] w-[calc(100%+24px)]" fill="none" aria-hidden>
            <ellipse cx="60" cy="20" rx="56" ry="17" stroke="#fbbf24" strokeWidth="3" pathLength={100}
              strokeDasharray={100} className="ms-cycle" style={{ animationName: 'msDraw', animationDelay: '1.2s' }} />
          </svg>
        </span>
      </div>
    </MiniFrame>
  )
}

function SceneSteps() {
  return (
    <MiniFrame title="Scène « étapes » — cascade numérotée">
      <span className="ms-cycle absolute left-1/2 top-[9%] -translate-x-1/2 rounded-full border border-amber-300/80 px-2.5 py-0.5 text-[9px] font-bold tracking-widest text-amber-300 opacity-0" style={{ animationName: 'msPop' }}>
        ÉTAPES
      </span>
      {['CRÉER LA BOUTIQUE', 'AJOUTER LES PRODUITS', 'ENCAISSER MOMO'].map((step, i) => (
        <div
          key={step}
          className="ms-cycle absolute left-1/2 flex w-[82%] -translate-x-1/2 items-center gap-2 rounded-full border border-cyan-300/60 bg-black/50 px-2 py-1.5 opacity-0"
          style={{ top: `${26 + i * 17}%`, animationName: 'msPop', animationDelay: `${0.5 + i * 0.45}s` }}
        >
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-400 text-[10px] font-extrabold text-black">{i + 1}</span>
          <span className="text-[10px] font-bold text-white">{step}</span>
        </div>
      ))}
      <svg viewBox="0 0 40 80" className="absolute bottom-[8%] right-[8%] h-[22%]" fill="none" aria-hidden>
        <path d="M30 74 Q34 40 12 16 M12 30 L10 12 L28 16" stroke="#22d3ee" strokeWidth="4" strokeLinecap="round"
          pathLength={100} strokeDasharray={100} className="ms-cycle"
          style={{ animationName: 'msDraw', animationDelay: '2s' }} />
      </svg>
    </MiniFrame>
  )
}

function useDemoCounterMini(target = 3) {
  const [value, setValue] = useState(target)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let raf = 0
    const tick = () => {
      const t = (performance.now() / 1000) % 7
      const p = Math.min(1, Math.max(0, (t - 1.0) / 1.3))
      setValue(Math.max(1, Math.round(target * (1 - Math.pow(1 - p, 3)))))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target])
  return value
}

function SceneNumber() {
  const counter = useDemoCounterMini()
  return (
    <MiniFrame title="Scène « chiffre » — compteur doré">
      <span className="ms-cycle absolute left-1/2 top-[9%] -translate-x-1/2 rounded-full border border-amber-300/80 px-2.5 py-0.5 text-[9px] font-bold tracking-widest text-amber-300 opacity-0" style={{ animationName: 'msPop' }}>
        CHIFFRE CLÉ
      </span>
      <svg viewBox="0 0 100 70" className="absolute left-1/2 top-[22%] h-[30%] w-[58%] -translate-x-1/2" fill="none" aria-hidden>
        <path d="M8 62 V10 M8 62 H92" stroke="#fff" strokeWidth="4" strokeLinecap="round"
          pathLength={100} strokeDasharray={100} className="ms-cycle" style={{ animationName: 'msDraw' }} />
        <path d="M14 54 L36 38 L52 44 L86 16 M70 16 L86 16 L86 32" stroke="#22d3ee" strokeWidth="4"
          strokeLinecap="round" strokeLinejoin="round" pathLength={100} strokeDasharray={100}
          className="ms-cycle" style={{ animationName: 'msDraw', animationDelay: '0.6s' }} />
      </svg>
      <div className="ms-cycle absolute left-1/2 top-[58%] -translate-x-1/2 text-center opacity-0" style={{ animationName: 'msPop', animationDelay: '1s' }}>
        <span className="font-display text-4xl font-bold text-amber-300">×{counter}</span>
        <p className="mt-1 text-[10px] font-bold tracking-widest text-white/80">TES VENTES</p>
      </div>
    </MiniFrame>
  )
}

/* ========================================================================== */
/*  Contenu                                                                   */
/* ========================================================================== */

const MARQUEE_ITEMS = [
  'DÉCOUPE INTELLIGENTE', 'MOTION DESIGN ILLUSTRÉ', 'B-ROLL IA', 'SOUS-TITRES KARAOKÉ',
  'SOUND DESIGN PRO', 'ZOOMS DYNAMIQUES', 'EXPORT 9:16', 'MOTS-CLÉS EN OR',
]

const FEATURES = [
  {
    icon: PenTool,
    title: 'Motion design illustré',
    text: "Les moments clés de ton discours deviennent des scènes animées : dessins qui se tracent, flèches, étapes numérotées, compteurs — avec transitions et effets sonores calés.",
  },
  {
    icon: Scissors,
    title: 'Découpe intelligente',
    text: "Silences, hésitations, faux départs et phrases répétées disparaissent. CutForge garde la bonne prise, sans jamais couper un mot au milieu.",
  },
  {
    icon: ImageIcon,
    title: 'B-roll IA sur mesure',
    text: "Des images générées qui montrent exactement ce que tu dis, au moment où tu le dis. Visages et décors africains par défaut — réglable avant chaque montage.",
  },
  {
    icon: Subtitles,
    title: 'Sous-titres karaoké',
    text: "Mot par mot, parfaitement synchronisés, 5 styles viraux au choix. Tes vidéos captivent même en sourdine.",
  },
  {
    icon: Volume2,
    title: 'Sound design professionnel',
    text: "27 sons forgés — captures photo, whoosh, risers, pops — variés automatiquement pour ne jamais entendre deux fois le même son.",
  },
  {
    icon: Smartphone,
    title: 'Prêt pour TikTok & Reels',
    text: "1080×1920 natif, zooms dynamiques, mots-clés dorés, export optimisé. Tu télécharges, tu publies, c'est tout.",
  },
]

const FAQ_ITEMS = [
  {
    q: 'Comment ça marche, concrètement ?',
    a: "Tu filmes une vidéo face caméra (le téléphone suffit), tu l'envoies sur CutForge et tu choisis un style. Le moteur transcrit ton discours mot par mot, coupe les silences et les ratés, illustre les passages importants en motion design, génère des B-rolls IA, ajoute sons et sous-titres, puis exporte un MP4 vertical prêt à publier.",
  },
  {
    q: 'Le montage prend combien de temps ?',
    a: "Quelques minutes selon la durée de ta vidéo. Tu peux fermer la page : le traitement continue sur nos serveurs et ton montage t'attend dans le dashboard.",
  },
  {
    q: 'Les images générées me ressemblent ?',
    a: "Par défaut, CutForge génère des visuels avec des personnes et des décors africains modernes (Abidjan, Dakar, Lomé, Douala…). Tu peux changer ce réglage avant chaque montage si tu vises une autre audience.",
  },
  {
    q: "C'est vraiment gratuit ?",
    a: "Oui : 2 vidéos par mois offertes, sans carte bancaire, avec toutes les fonctions de montage. Le plan Pro débloque plus de vidéos, des durées plus longues et la priorité de rendu.",
  },
  {
    q: 'Quels formats de vidéo sont acceptés ?',
    a: "MP4, MOV, WebM, MKV, AVI et la plupart des formats mobiles — jusqu'à plusieurs Go. L'upload est optimisé pour les connexions mobiles.",
  },
]

/* ========================================================================== */
/*  Page                                                                      */
/* ========================================================================== */

export default function Landing() {
  const heroRef = useRef<HTMLDivElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const el = heroRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    el.style.setProperty('--mx', (((e.clientX - rect.left) / rect.width - 0.5) * 2).toFixed(3))
    el.style.setProperty('--my', (((e.clientY - rect.top) / rect.height - 0.5) * 2).toFixed(3))
  }, [])

  return (
    <div className="overflow-x-clip">
      {/* ================= HERO ================= */}
      <section
        ref={heroRef}
        onMouseMove={handleMouseMove}
        className="relative isolate overflow-hidden"
      >
        {/* fond animé */}
        <div className="absolute inset-0 -z-10" aria-hidden>
          <div className="cf-aurora left-[-10%] top-[-15%] h-[480px] w-[480px] bg-primary-600/60" />
          <div className="cf-aurora right-[-12%] top-[10%] h-[420px] w-[420px] bg-fuchsia-600/40" style={{ animationDelay: '-6s' }} />
          <div className="cf-aurora bottom-[-20%] left-[25%] h-[460px] w-[460px] bg-accent-500/30" style={{ animationDelay: '-11s' }} />
          <div className="cf-grid-dots absolute inset-0" />
        </div>

        <div className="mx-auto grid max-w-7xl items-center gap-14 px-4 pb-20 pt-16 sm:px-6 lg:grid-cols-2 lg:gap-8 lg:px-8 lg:pt-24">
          {/* copy */}
          <div className="cf-parallax" style={{ '--px': '6px', '--py': '4px' } as React.CSSProperties}>
            <Reveal>
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-dark-200">
                <Logo size={18} />
                <span className="font-semibold tracking-wide">{BRAND.name}</span>
                <span className="h-1 w-1 rounded-full bg-dark-500" />
                <span className="text-dark-300">Le moteur de montage IA</span>
              </div>
            </Reveal>

            <Reveal delay={80}>
              <h1 className="text-balance text-4xl font-bold leading-[1.05] sm:text-5xl lg:text-6xl">
                Une vidéo brute entre.
                <br />
                <span className="gradient-text">Un montage de pro</span> ressort.
              </h1>
            </Reveal>

            <Reveal delay={160}>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-dark-300">
                {BRAND.name} coupe les silences et les ratés, <strong className="text-white">illustre tes propos
                en motion design</strong>, ajoute B-rolls IA, sous-titres karaoké et sound design —
                ta vidéo est prête pour TikTok, Reels et Shorts en quelques minutes.
              </p>
            </Reveal>

            <Reveal delay={240}>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link to="/signup" className="btn-accent inline-flex items-center justify-center gap-2 px-7 py-3.5 text-base">
                  <Zap className="h-5 w-5" />
                  Créer mon premier montage
                </Link>
                <a href="#comment" className="btn-secondary inline-flex items-center justify-center gap-2 px-7 py-3.5 text-base">
                  Voir comment ça marche
                  <ArrowRight className="h-4 w-4" />
                </a>
              </div>
            </Reveal>

            <Reveal delay={320}>
              <ul className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-dark-300">
                {['Sans carte bancaire', '2 vidéos offertes / mois', "Pensé pour l'Afrique francophone"].map((t) => (
                  <li key={t} className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-400" />
                    {t}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>

          {/* simulation */}
          <Reveal delay={200}>
            <div className="cf-parallax" style={{ '--px': '-14px', '--py': '-10px' } as React.CSSProperties}>
              <PhoneDemo />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ================= MARQUEE ================= */}
      <section className="border-y border-white/5 bg-dark-900/40 py-5">
        <div className="mask-fade-x overflow-hidden">
          <div className="cf-marquee flex w-max gap-10">
            {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, i) => (
              <span key={i} className="flex items-center gap-10 whitespace-nowrap text-sm font-bold tracking-[0.2em] text-dark-400">
                {item}
                <Sparkles className="h-4 w-4 text-primary-500/70" />
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ================= AVANT / APRÈS (scroll + curseur) ================= */}
      <BeforeAfter />

      {/* ================= COMMENT ÇA MARCHE ================= */}
      <section id="comment" className="relative mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Du brut au viral en <span className="gradient-text">3 étapes</span>
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-dark-300">
            Pas de timeline, pas de logiciel à apprendre. Tu parles, {BRAND.name} forge.
          </p>
        </Reveal>

        <Reveal className="relative mt-16">
          {/* connecteur dessiné entre les étapes */}
          <svg className="cf-connector absolute left-0 right-0 top-10 hidden h-8 w-full lg:block" viewBox="0 0 1000 40" fill="none" preserveAspectRatio="none" aria-hidden>
            <path d="M170 20 C 320 -10, 420 50, 500 20 S 720 -10, 830 20" stroke="url(#cf-line)" strokeWidth="2.5" strokeDasharray="8 7" pathLength={100} />
            <defs>
              <linearGradient id="cf-line" x1="0" y1="0" x2="1000" y2="0" gradientUnits="userSpaceOnUse">
                <stop stopColor="#3f72ff" />
                <stop offset="1" stopColor="#f97316" />
              </linearGradient>
            </defs>
          </svg>

          <div className="grid gap-10 lg:grid-cols-3">
            {[
              {
                icon: Upload, step: '01', title: 'Envoie ta vidéo parlée',
                text: 'Filme face caméra avec ton téléphone — lumière correcte, voix claire. Pas besoin de matériel pro.',
              },
              {
                icon: Wand2, step: '02', title: `${BRAND.name} forge le montage`,
                text: 'Transcription mot par mot, coupes intelligentes, scènes motion design, B-roll IA, sons et sous-titres calés à la milliseconde.',
              },
              {
                icon: Smartphone, step: '03', title: "Publie et capte l'attention",
                text: 'Télécharge ton MP4 vertical 1080×1920 prêt pour TikTok, Reels et Shorts. En minutes, pas en heures.',
              },
            ].map(({ icon: Icon, step, title, text }, i) => (
              <Reveal key={step} delay={i * 120}>
                <div className="cf-card card relative z-10 h-full text-center">
                  <span className="absolute right-5 top-4 font-display text-4xl font-bold text-white/5">{step}</span>
                  <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary-600 to-fuchsia-500 shadow-lg shadow-primary-900/50">
                    <Icon className="h-7 w-7 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold">{title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-dark-300">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ================= VITRINE MOTION DESIGN ================= */}
      <section className="relative border-y border-white/5 bg-gradient-to-b from-dark-900/40 to-transparent py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Reveal className="text-center">
            <span className="rounded-full border border-amber-300/40 bg-amber-300/10 px-4 py-1 text-xs font-bold tracking-widest text-amber-300">
              LA SIGNATURE {BRAND.name.toUpperCase()}
            </span>
            <h2 className="mt-5 text-3xl font-bold sm:text-4xl">
              Ton discours, <span className="gradient-text">dessiné à l'écran</span>
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-dark-300">
              Quand tu expliques un point important, une scène motion design prend l'écran :
              illustrations qui se tracent, flèches, étapes, compteurs — avec une transition
              et des effets sonores. Comme chez les monteurs pros, automatiquement.
            </p>
          </Reveal>

          <div className="mt-14 grid gap-10 sm:grid-cols-3">
            <Reveal delay={0}><SceneIdea /></Reveal>
            <Reveal delay={120}><SceneSteps /></Reveal>
            <Reveal delay={240}><SceneNumber /></Reveal>
          </div>
        </div>
      </section>

      {/* ================= FEATURES ================= */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Tout ce qu'un monteur pro ferait. <span className="gradient-text">Sans le monteur.</span>
          </h2>
        </Reveal>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }, i) => (
            <Reveal key={title} delay={(i % 3) * 100}>
              <div
                className="cf-card card h-full"
                onMouseMove={(e) => {
                  const r = e.currentTarget.getBoundingClientRect()
                  e.currentTarget.style.setProperty('--gx', `${e.clientX - r.left}px`)
                  e.currentTarget.style.setProperty('--gy', `${e.clientY - r.top}px`)
                }}
              >
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600/15 text-primary-400">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-2.5 text-sm leading-relaxed text-dark-300">{text}</p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* bande de stats produit */}
        <Reveal delay={150}>
          <div className="mt-16 grid grid-cols-2 gap-6 rounded-2xl border border-white/10 bg-dark-900/60 p-8 text-center sm:grid-cols-4">
            {[
              ['−80%', 'de temps de montage'],
              ['1080×1920', 'vertical natif 30 fps'],
              ['27', 'effets sonores forgés'],
              ['5', 'styles de sous-titres'],
            ].map(([big, small]) => (
              <div key={small}>
                <p className="gradient-text font-display text-3xl font-bold">{big}</p>
                <p className="mt-1 text-sm text-dark-400">{small}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* ================= PRICING TEASER ================= */}
      <section className="mx-auto max-w-5xl px-4 pb-24 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <h2 className="text-3xl font-bold sm:text-4xl">Commence gratuitement</h2>
          <p className="mt-4 text-dark-300">Paiement en FCFA via Mobile Money, ou en dollars. Annulable à tout moment.</p>
        </Reveal>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <Reveal>
            <div className="card h-full">
              <h3 className="font-semibold text-dark-200">Découverte</h3>
              <p className="mt-3 font-display text-4xl font-bold">0 <span className="text-base font-normal text-dark-400">FCFA</span></p>
              <ul className="mt-6 space-y-2.5 text-sm text-dark-300">
                {['2 vidéos par mois', '5 min max par vidéo', 'Motion design + B-roll IA inclus', 'Sous-titres karaoké & SFX'].map((f) => (
                  <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-emerald-400" />{f}</li>
                ))}
              </ul>
              <Link to="/signup" className="btn-secondary mt-8 block w-full text-center">Commencer gratuitement</Link>
            </div>
          </Reveal>
          <Reveal delay={120}>
            <div className="card relative h-full border-primary-500/40 bg-gradient-to-b from-primary-950/40 to-dark-900">
              <span className="absolute -top-3 left-6 rounded-full bg-accent-500 px-3 py-0.5 text-xs font-bold text-white">POPULAIRE</span>
              <h3 className="font-semibold text-dark-200">Pro</h3>
              <p className="mt-3 font-display text-4xl font-bold">5 000 <span className="text-base font-normal text-dark-400">FCFA / mois</span></p>
              <ul className="mt-6 space-y-2.5 text-sm text-dark-300">
                {['Plus de vidéos chaque mois', '30 min max par vidéo', 'Priorité de rendu', 'Tous les styles & réglages avancés'].map((f) => (
                  <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-emerald-400" />{f}</li>
                ))}
              </ul>
              <Link to="/pricing" className="btn-primary mt-8 block w-full text-center">Voir tous les tarifs</Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ================= FAQ ================= */}
      <section className="mx-auto max-w-3xl px-4 pb-24 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <h2 className="text-3xl font-bold">Questions fréquentes</h2>
        </Reveal>
        <div className="mt-10 space-y-3">
          {FAQ_ITEMS.map(({ q, a }, i) => (
            <Reveal key={q} delay={i * 60}>
              <details className="group rounded-xl border border-white/10 bg-dark-900/60 px-5 py-4 [&_summary::-webkit-details-marker]:hidden">
                <summary className="flex cursor-pointer items-center justify-between gap-4 font-medium text-dark-100">
                  {q}
                  <ChevronDown className="h-4 w-4 shrink-0 text-dark-400 transition-transform group-open:rotate-180" />
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-dark-300">{a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ================= CTA FINAL ================= */}
      <section className="mx-auto max-w-7xl px-4 pb-28 sm:px-6 lg:px-8">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-tr from-primary-950 via-dark-900 to-[#2a1230] px-8 py-16 text-center">
            <div className="cf-aurora left-[10%] top-[-40%] h-[300px] w-[300px] bg-primary-500/50" aria-hidden />
            <div className="cf-aurora bottom-[-50%] right-[5%] h-[320px] w-[320px] bg-accent-500/40" style={{ animationDelay: '-7s' }} aria-hidden />
            <div className="relative">
              <div className="mx-auto mb-6 w-fit"><Logo size={52} /></div>
              <h2 className="text-balance text-3xl font-bold sm:text-4xl">
                Prêt à forger ton prochain montage ?
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-dark-300">
                Envoie ta première vidéo maintenant — dans quelques minutes, tu télécharges
                un montage avec motion design, B-roll, sons et sous-titres.
              </p>
              <Link to="/signup" className="btn-accent mt-8 inline-flex items-center gap-2 px-8 py-4 text-base">
                <Zap className="h-5 w-5" />
                Lancer {BRAND.name} gratuitement
              </Link>
            </div>
          </div>
        </Reveal>
      </section>

      <Footer />
    </div>
  )
}
