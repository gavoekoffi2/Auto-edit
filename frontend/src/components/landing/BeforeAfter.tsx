import { useEffect, useRef } from 'react'
import { Check, MousePointer2, X } from 'lucide-react'
import Logo from '../ui/Logo'
import Reveal from '../ui/Reveal'

/* ===========================================================================
   AVANT / APRÈS — le montage se fait sous tes yeux.

   Une section "sticky" : le scroll naturel de la page déplace la lame
   CutForge sur le téléphone (aucun détournement du scroll — règle UX), et
   quand le curseur survole le téléphone, c'est lui qui prend la main.
   À gauche la vidéo brute (tremblante, silences, « euh »), à droite le
   montage (grade chaud, captions karaoké, scène motion design, SFX).
   Tout est piloté par UNE variable CSS --ba ∈ [0,1], lissée en rAF.
   ======================================================================== */

const clamp01 = (v: number) => Math.min(1, Math.max(0, v))

/** opacité dérivée de --ba : 0 avant `from`, 1 après `from + 0.18` */
const gate = (from: number): React.CSSProperties => ({
  opacity: `clamp(0, calc((var(--ba) - ${from}) * 5.5), 1)`,
  transform: `translateX(calc(clamp(0, calc((var(--ba) - ${from}) * 5.5), 1) * 0px))`,
})

function useBeforeAfterProgress(
  outerRef: React.RefObject<HTMLDivElement>,
  stageRef: React.RefObject<HTMLDivElement>,
) {
  const hover = useRef<number | null>(null)

  useEffect(() => {
    const outer = outerRef.current
    const stage = stageRef.current
    if (!outer || !stage) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      stage.style.setProperty('--ba', '0.5')
      return
    }

    let raf = 0
    let current = 0.12
    let active = false

    const tick = () => {
      const rect = outer.getBoundingClientRect()
      const total = Math.max(1, rect.height - window.innerHeight)
      const scrollP = clamp01(-rect.top / total)
      // Le scroll raconte l'histoire ; le curseur, lui, prend la main.
      const target = hover.current ?? (0.06 + scrollP * 0.92)
      current += (target - current) * 0.14
      stage.style.setProperty('--ba', current.toFixed(4))
      if (active) raf = requestAnimationFrame(tick)
    }

    // n'anime que quand la section est proche du viewport (CPU friendly)
    const io = new IntersectionObserver(([entry]) => {
      active = entry.isIntersecting
      cancelAnimationFrame(raf)
      if (active) raf = requestAnimationFrame(tick)
    }, { rootMargin: '20% 0px' })
    io.observe(outer)

    return () => {
      io.disconnect()
      cancelAnimationFrame(raf)
    }
  }, [outerRef, stageRef])

  return {
    onPointerMove: (e: React.PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      const rect = e.currentTarget.getBoundingClientRect()
      hover.current = clamp01((e.clientX - rect.left) / rect.width)
    },
    onPointerLeave: () => { hover.current = null },
  }
}

/* ---------- côté AVANT : la vidéo brute ---------------------------------- */
function RawSide() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-[#15171c]">
      <div className="ba-wobble absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-[#262a33] via-[#21242d] to-[#14161c]" />
        {/* silhouette terne */}
        <svg viewBox="0 0 100 178" className="absolute inset-x-0 bottom-0 mx-auto h-[72%] opacity-80" aria-hidden>
          <ellipse cx="50" cy="58" rx="20" ry="22" fill="#4a4038" />
          <path d="M14 178 Q16 112 50 108 Q84 112 86 178 Z" fill="#3a3f4a" />
          <path d="M40 96 q10 10 20 0 l0 14 q-10 8 -20 0 Z" fill="#4a4038" />
        </svg>
        {/* grain */}
        <div className="noise absolute inset-0" />
      </div>

      {/* REC + timecode */}
      <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/55 px-2 py-1 text-[10px] font-bold tracking-widest text-red-400">
        <span className="ba-rec h-2 w-2 rounded-full bg-red-500" />
        REC&nbsp;00:04:12
      </div>

      {/* hésitations */}
      <span className="ba-uh absolute left-[14%] top-[30%] rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-semibold text-dark-300">euh…</span>
      <span className="ba-uh absolute right-[12%] top-[42%] rounded-full bg-black/60 px-2.5 py-1 text-[11px] font-semibold text-dark-300" style={{ animationDelay: '2.4s' }}>donc… voilà</span>

      {/* timeline pleine de déchets */}
      <div className="absolute inset-x-4 bottom-4">
        <p className="mb-1.5 text-[9px] font-bold tracking-widest text-dark-400">RUSH BRUT — 4:12</p>
        <div className="flex h-2.5 gap-0.5 overflow-hidden rounded">
          {[8, 14, 5, 18, 7, 12, 6, 16, 9, 5].map((w, i) => (
            <span
              key={i}
              style={{ width: `${w}%` }}
              className={i % 2 === 0 ? 'bg-dark-500/80' : 'bg-red-500/45'}
            />
          ))}
        </div>
        <p className="mt-1 text-[9px] text-red-400/80">■ silences, ratés &amp; répétitions</p>
      </div>
    </div>
  )
}

/* ---------- côté APRÈS : le montage CutForge ------------------------------ */
function EditedSide() {
  return (
    <div className="ba-after absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-[#1d2440] via-[#232b52] to-[#101326]" />
      <svg viewBox="0 0 100 178" className="absolute inset-x-0 bottom-0 mx-auto h-[72%]" aria-hidden>
        <ellipse cx="50" cy="58" rx="20" ry="22" fill="#5a4634" />
        <path d="M14 178 Q16 112 50 108 Q84 112 86 178 Z" fill="#2a55f5" />
        <path d="M40 96 q10 10 20 0 l0 14 q-10 8 -20 0 Z" fill="#5a4634" />
      </svg>

      {/* mini scène motion design en haut */}
      <div className="absolute left-1/2 top-[9%] w-[78%] -translate-x-1/2 rounded-xl border border-cyan-300/40 bg-[#0b0e1a]/90 p-2.5">
        <div className="flex items-center justify-between">
          <span className="rounded-full border border-amber-300/70 px-1.5 py-0.5 text-[8px] font-bold tracking-widest text-amber-300">CHIFFRE CLÉ</span>
          <span className="font-display text-lg font-bold text-amber-300">80%</span>
        </div>
        <svg viewBox="0 0 100 26" className="mt-1.5 h-6 w-full" fill="none" aria-hidden>
          <path d="M4 22 L30 14 L52 18 L96 4 M82 4 L96 4 L96 14" stroke="#22d3ee" strokeWidth="3"
            strokeLinecap="round" strokeLinejoin="round" pathLength={100} strokeDasharray={100}
            className="ms-cycle" style={{ animationName: 'msDraw' }} />
        </svg>
      </div>

      {/* coins viseur */}
      <div className="absolute inset-3" aria-hidden>
        <span className="absolute left-0 top-0 h-4 w-4 border-l-2 border-t-2 border-cyan-300/80" />
        <span className="absolute right-0 top-0 h-4 w-4 border-r-2 border-t-2 border-cyan-300/80" />
        <span className="absolute bottom-0 left-0 h-4 w-4 border-b-2 border-l-2 border-cyan-300/80" />
        <span className="absolute bottom-0 right-0 h-4 w-4 border-b-2 border-r-2 border-cyan-300/80" />
      </div>

      {/* captions karaoké */}
      <div className="absolute inset-x-0 bottom-[18%] flex justify-center">
        <div className="ba-cap absolute flex gap-1 font-display text-[15px] font-bold">
          {['LA', 'MÉTHODE', 'SIMPLE'].map((w, i) => (
            <span key={w} className="ba-word text-white drop-shadow-[0_2px_0_rgba(0,0,0,0.8)]" style={{ animationDelay: `${i * 0.8}s` }}>{w}</span>
          ))}
        </div>
        <div className="ba-cap ba-cap-late absolute flex gap-1 font-display text-[15px] font-bold">
          {['POUR', 'VENDRE', 'PLUS'].map((w, i) => (
            <span key={w} className="ba-word text-white drop-shadow-[0_2px_0_rgba(0,0,0,0.8)]" style={{ animationDelay: `${2.5 + i * 0.8}s` }}>{w}</span>
          ))}
        </div>
      </div>

      {/* timeline propre */}
      <div className="absolute inset-x-4 bottom-4">
        <p className="mb-1.5 text-[9px] font-bold tracking-widest text-cyan-200">MONTAGE CUTFORGE — 2:36</p>
        <div className="flex h-2.5 gap-0.5 overflow-hidden rounded">
          {[22, 18, 26, 20, 14].map((w, i) => (
            <span key={i} style={{ width: `${w}%` }} className="bg-gradient-to-r from-primary-400 to-cyan-300" />
          ))}
        </div>
        <p className="mt-1 text-[9px] text-emerald-300/90">✓ seulement les bonnes prises</p>
      </div>
    </div>
  )
}

/* ---------- la section ----------------------------------------------------- */
const BEFORE_POINTS = [
  'Silences et blancs interminables',
  '« euh… », faux départs, répétitions',
  'Image plate, zéro habillage',
  'Personne ne reste après 3 secondes',
]

const AFTER_POINTS: Array<[string, number]> = [
  ['Silences & ratés coupés au mot près', 0.30],
  ['Motion design qui illustre le discours', 0.48],
  ['Sous-titres karaoké + mots-clés dorés', 0.64],
  ['Sound design pro calé sur chaque effet', 0.80],
]

export default function BeforeAfter() {
  const outerRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const pointerHandlers = useBeforeAfterProgress(outerRef, stageRef)

  return (
    <section ref={outerRef} className="relative h-[260vh]" id="avant-apres">
      <div className="sticky top-0 flex min-h-screen items-center overflow-hidden">
        {/* fond */}
        <div className="absolute inset-0 -z-10" aria-hidden>
          <div className="cf-aurora left-[-12%] top-[8%] h-[420px] w-[420px] bg-primary-600/40" />
          <div className="cf-aurora right-[-10%] bottom-[5%] h-[380px] w-[380px] bg-accent-500/25" style={{ animationDelay: '-8s' }} />
        </div>

        <div ref={stageRef} className="ba-stage mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
          <Reveal className="text-center">
            <span className="rounded-full border border-white/10 bg-white/5 px-4 py-1 text-xs font-bold tracking-widest text-dark-300">
              AVANT / APRÈS
            </span>
            <h2 className="mt-5 text-3xl font-bold sm:text-5xl">
              Regarde le montage <span className="gradient-text">se faire sous tes yeux</span>
            </h2>
          </Reveal>

          <div className="mt-10 grid items-center gap-8 lg:grid-cols-[1fr_auto_1fr]">
            {/* colonne AVANT */}
            <div
              className="order-2 lg:order-1 lg:text-right"
              style={{ opacity: 'calc(1 - var(--ba) * 0.72)' }}
            >
              <p className="font-display text-2xl font-bold text-dark-300">AVANT</p>
              <p className="mb-5 font-display text-4xl font-bold text-dark-500">4:12</p>
              <ul className="space-y-3 text-sm text-dark-400">
                {BEFORE_POINTS.map((t) => (
                  <li key={t} className="flex items-center gap-2.5 lg:flex-row-reverse">
                    <X className="h-4 w-4 shrink-0 text-red-400/80" />
                    {t}
                  </li>
                ))}
              </ul>
            </div>

            {/* le téléphone, coupé par la lame */}
            <Reveal className="order-1 lg:order-2">
              <div
                className="relative mx-auto w-[260px] cursor-ew-resize touch-pan-y sm:w-[290px]"
                {...pointerHandlers}
              >
                <div
                  className="absolute -inset-8 rounded-[3rem] blur-2xl"
                  style={{ background: 'linear-gradient(105deg, rgba(120,120,135,0.25) 0%, rgba(63,114,255,0.3) 60%, rgba(249,115,22,0.3) 100%)' }}
                  aria-hidden
                />
                <div className="relative rounded-[2.4rem] border border-white/15 bg-dark-900 p-2 shadow-2xl">
                  <div className="relative aspect-[9/16] overflow-hidden rounded-[1.9rem]">
                    <RawSide />
                    <EditedSide />

                    {/* la lame CutForge */}
                    <div className="ba-blade pointer-events-none absolute inset-y-0 z-30 w-10" aria-hidden>
                      <div className="ba-blade-line absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2" />
                      <span className="ba-spark absolute left-1/2 top-[20%] h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-cyan-200" />
                      <span className="ba-spark absolute left-1/2 top-[64%] h-1 w-1 -translate-x-1/2 rounded-full bg-amber-200" style={{ animationDelay: '0.7s' }} />
                      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/30 bg-dark-950/90 p-1.5 shadow-xl">
                        <Logo size={22} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* étiquettes flottantes */}
                <span className="absolute -left-4 top-6 rounded-md bg-black/70 px-2 py-0.5 text-[10px] font-bold tracking-widest text-dark-300" style={{ opacity: 'calc(1 - var(--ba))' }}>
                  BRUT
                </span>
                <span className="absolute -right-4 top-6 rounded-md bg-accent-500/90 px-2 py-0.5 text-[10px] font-bold tracking-widest text-white" style={{ opacity: 'var(--ba)' }}>
                  CUTFORGE
                </span>
              </div>
            </Reveal>

            {/* colonne APRÈS */}
            <div className="order-3" style={{ opacity: 'calc(0.35 + var(--ba) * 0.65)' }}>
              <p className="font-display text-2xl font-bold text-white">APRÈS</p>
              <p className="mb-5 font-display text-4xl font-bold gradient-text">2:36</p>
              <ul className="space-y-3 text-sm">
                {AFTER_POINTS.map(([t, threshold]) => (
                  <li key={t} className="ba-check flex items-center gap-2.5 text-dark-100" style={gate(threshold)}>
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-400/15">
                      <Check className="h-3.5 w-3.5 text-emerald-300" />
                    </span>
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <p className="ba-hint mx-auto mt-10 flex w-fit items-center gap-2 text-sm text-dark-400">
            <MousePointer2 className="h-4 w-4" />
            Scrolle — ou glisse ton curseur sur la vidéo
          </p>
        </div>
      </div>
    </section>
  )
}
