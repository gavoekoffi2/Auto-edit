import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowRight, Check, Clapperboard, Download, Film, ImagePlus, Loader2, Music2, RefreshCw,
  Shuffle, Sparkles, Subtitles, Upload, Wand2, X,
} from 'lucide-react'
import StylePreview from '../components/studio/StylePreview'
import {
  listStudioStyles, logoUrl, MONTAGE_LABELS, STUDIO_STEPS, uploadLogo,
  type MontageId, type RecentStyle, type StudioStyle,
} from '../api/studio'
import { createJob, downloadJobResult, getJobDownloadUrl, cancelJob } from '../api/jobs'
import { getVideo, listVideos, validateVideoFile } from '../api/videos'
import { useVideoUpload } from '../hooks/useVideoUpload'
import { useJobPolling } from '../hooks/useJobPolling'
import { getErrorMessage } from '../api/client'
import { toast } from '../components/ui/Toast'
import '../styles/studio.css'

type Choice = 'auto' | 'invent' | string
type Density = 'light' | 'medium' | 'heavy'

interface VideoItem { id: string; title: string; duration_s: number | null; status?: string }

const ease = [0.16, 1, 0.3, 1] as const
const fadeUp = { initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -12 }, transition: { duration: 0.6, ease } }

const DEMO_PALETTES = [
  { dark: '#0A1628', dark2: '#1B2B45', light: '#FAF3E3', light2: '#EFE3C8', ink: '#1A1A2E', accent: '#E63946', accent2: '#D4A843', bad: '#E23A3A', good: '#2DBE6C' },
  { dark: '#05020F', dark2: '#1A0B3D', light: '#F7F5FF', light2: '#E4DEFF', ink: '#140A33', accent: '#22E3FF', accent2: '#FF3D8B', bad: '#FF3D8B', good: '#2DBE6C' },
  { dark: '#0B1020', dark2: '#1C2440', light: '#FFFFFF', light2: '#EEF2F8', ink: '#0F172A', accent: '#2F7BFF', accent2: '#34C759', bad: '#E23A3A', good: '#2DBE6C' },
]

function fmt(s: number | null | undefined) {
  if (!s && s !== 0) return '—'
  const m = Math.floor(s / 60), r = Math.round(s % 60)
  return m ? `${m} min ${String(r).padStart(2, '0')}` : `${r} s`
}

/* ------------------------------------------------------------------ en-tête */
function Hero() {
  return (
    <div className="relative overflow-hidden rounded-[28px] border border-white/[0.07] bg-dark-900/60 px-6 py-10 sm:px-10 sm:py-14">
      <div className="studio-orbit left-[-10%] top-[-40%] h-72 w-72 bg-primary-600" />
      <div className="studio-orbit right-[-5%] bottom-[-50%] h-80 w-80 bg-accent-500" style={{ animationDelay: '-6s' }} />
      <div className="absolute inset-0 cf-grid-dots opacity-60" />
      <div className="relative grid items-center gap-10 lg:grid-cols-[1.15fr_1fr]">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold tracking-wide text-primary-200">
            <Clapperboard className="h-3.5 w-3.5" /> Studio face caméra
          </span>
          <h1 className="mt-5 text-4xl font-bold leading-[1.05] sm:text-5xl text-balance">
            Ta vidéo face caméra, montée comme un <span className="gradient-text">studio de motion design</span>.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-dark-300 sm:text-lg">
            Coupes au ras de la voix, idées écrites à l’écran au mot près, démonstrations animées, effets sonores,
            musique, logo. Et une <b className="text-white">grammaire de montage différente à chaque vidéo</b> :
            jamais deux montages qui se ressemblent.
          </p>
          <div className="mt-7 flex flex-wrap gap-2 text-xs text-dark-300">
            {['16 modes de montage', '20 directions artistiques', 'styles inventés', 'anti-répétition'].map((t) => (
              <span key={t} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5">{t}</span>
            ))}
          </div>
        </div>
        <div className="relative mx-auto flex h-[300px] w-full max-w-[420px] items-end justify-center gap-3">
          {(['telephone', 'kinetique', 'mur_polaroid'] as MontageId[]).map((m, i) => (
            <motion.div
              key={m}
              className="w-[31%] overflow-hidden rounded-2xl border border-white/10 shadow-card-premium"
              initial={{ opacity: 0, y: 40, rotate: 0 }}
              animate={{ opacity: 1, y: i === 1 ? -26 : 0, rotate: i === 0 ? -5 : i === 2 ? 5 : 0 }}
              transition={{ delay: 0.15 + i * 0.12, duration: 0.9, ease }}
            >
              <StylePreview montage={m} palette={DEMO_PALETTES[i]} headFont={i === 1 ? 'Bebas' : 'DMSerif'} />
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ étape numérotée */
function Step({ n, title, hint, done, children }: { n: number; title: string; hint?: string; done?: boolean; children: React.ReactNode }) {
  return (
    <motion.section {...fadeUp} className="relative rounded-[24px] border border-white/[0.07] bg-dark-900/50 p-5 sm:p-8">
      <header className="mb-6 flex items-start gap-4">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold transition-colors ${done ? 'bg-emerald-400/15 text-emerald-300' : 'bg-primary-500/15 text-primary-200'}`}>
          {done ? <Check className="h-5 w-5" /> : n}
        </div>
        <div>
          <h2 className="text-xl font-semibold sm:text-2xl">{title}</h2>
          {hint && <p className="mt-1 text-sm text-dark-400">{hint}</p>}
        </div>
      </header>
      {children}
    </motion.section>
  )
}

/* ------------------------------------------------------------------ carte de style */
function StyleCard({ style, selected, recent, onClick }: { style: StudioStyle; selected: boolean; recent: boolean; onClick: () => void }) {
  const [hover, setHover] = useState(false)
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      data-selected={selected}
      className="style-card group relative w-full min-w-0 rounded-2xl border border-white/[0.08] bg-dark-900 p-2.5 text-left"
    >
      <StylePreview montage={style.montage} palette={style.palette} headFont={style.head_font} playing={hover || selected} />
      <div className="px-1.5 pb-1 pt-3">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold">{style.name}</span>
          <span className="flex shrink-0 gap-1">
            {[style.palette.accent, style.palette.accent2, style.palette.dark].map((c) => (
              <i key={c} className="h-2.5 w-2.5 rounded-full ring-1 ring-white/20" style={{ background: c }} />
            ))}
          </span>
        </div>
        <div className="mt-1 text-[11px] font-medium uppercase tracking-[0.12em] text-primary-300/90">{style.montage_name}</div>
        <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-dark-400">{style.montage_desc}</p>
      </div>
      {recent && (
        <span className="absolute left-4 top-4 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-amber-200 backdrop-blur">
          utilisé récemment
        </span>
      )}
      {selected && (
        <span className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-full bg-primary-500 shadow-glow-primary">
          <Check className="h-4 w-4" />
        </span>
      )}
    </button>
  )
}

/* ------------------------------------------------------------------ choix « magique » */
function MagicChoice({ active, onClick, icon, title, text }: { active: boolean; onClick: () => void; icon: React.ReactNode; title: string; text: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-selected={active}
      className="style-card relative flex items-start gap-4 overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-br from-dark-900 to-dark-900/40 p-5 text-left"
    >
      <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${active ? 'bg-primary-500 text-white' : 'bg-white/5 text-primary-200'}`}>{icon}</div>
      <div>
        <div className="font-semibold">{title}</div>
        <p className="mt-1 text-sm leading-relaxed text-dark-400">{text}</p>
      </div>
      {active && <span className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full bg-primary-500"><Check className="h-3.5 w-3.5" /></span>}
    </button>
  )
}

/* ------------------------------------------------------------------ suivi du rendu */
function RenderProgress({ progress, status, error, onCancel }: { progress: number; status: string; error?: string | null; onCancel: () => void }) {
  const active = STUDIO_STEPS.reduce((k, s, i) => (progress >= s.at ? i : k), 0)
  const R = 58, C = 2 * Math.PI * R
  return (
    <div className="grid items-center gap-10 lg:grid-cols-[260px_1fr]">
      <div className="relative mx-auto h-[260px] w-[260px]">
        <svg viewBox="0 0 140 140" className="h-full w-full -rotate-90">
          <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="8" />
          <circle className="studio-progress-ring" cx="70" cy="70" r={R} fill="none" stroke="url(#sg)" strokeWidth="8" strokeLinecap="round"
            strokeDasharray={C} strokeDashoffset={C * (1 - Math.max(0.02, progress / 100))} />
          <defs><linearGradient id="sg" x1="0" x2="1"><stop offset="0" stopColor="#6593ff" /><stop offset="1" stopColor="#fb923c" /></linearGradient></defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="font-display text-5xl font-bold tabular-nums">{Math.round(progress)}<span className="text-2xl text-dark-400">%</span></div>
          <div className="mt-1 text-xs uppercase tracking-[0.18em] text-dark-400">{status === 'pending' ? 'en file' : 'en montage'}</div>
        </div>
      </div>
      <div>
        <ol className="space-y-2">
          {STUDIO_STEPS.map((s, i) => {
            const state = i < active ? 'done' : i === active ? 'now' : 'todo'
            return (
              <li key={s.label} className={`relative flex items-center gap-4 overflow-hidden rounded-xl border px-4 py-3 transition-colors ${state === 'now' ? 'border-primary-500/40 bg-primary-500/[0.07]' : 'border-white/[0.05] bg-white/[0.015]'}`}>
                {state === 'now' && <div className="studio-scan absolute inset-x-0 top-0 h-1/3" />}
                <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${state === 'done' ? 'bg-emerald-400/15 text-emerald-300' : state === 'now' ? 'bg-primary-500 text-white' : 'bg-white/5 text-dark-500'}`}>
                  {state === 'done' ? <Check className="h-4 w-4" /> : state === 'now' ? <Loader2 className="h-4 w-4 animate-spin" /> : i + 1}
                </span>
                <div className="min-w-0">
                  <div className={`text-sm font-semibold ${state === 'todo' ? 'text-dark-500' : ''}`}>{s.label}</div>
                  <div className="truncate text-xs text-dark-400">{s.hint}</div>
                </div>
              </li>
            )
          })}
        </ol>
        {error && <p className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        <button onClick={onCancel} className="mt-5 text-sm text-dark-400 underline-offset-4 hover:text-white hover:underline">Annuler le montage</button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ résultat */
function Result({ jobId, result, onAgain }: { jobId: string; result: Record<string, any>; onAgain: () => void }) {
  const st = result?.style || {}
  const pal = st.palette
  const plan: { type: string; layout: string }[] = result?.plan || []
  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,380px)_1fr]">
      <motion.div initial={{ opacity: 0, scale: 0.94, rotate: -2 }} animate={{ opacity: 1, scale: 1, rotate: 0 }} transition={{ duration: 0.9, ease }}
        className="mx-auto w-full max-w-[360px] rounded-[42px] border-[10px] border-[#0d0d10] bg-black shadow-card-premium">
        <video src={getJobDownloadUrl(jobId)} controls playsInline className="aspect-[9/16] w-full rounded-[32px] bg-black" />
      </motion.div>
      <div className="flex flex-col justify-center">
        <span className="status-pill w-fit" data-tone="ok"><Check className="h-3.5 w-3.5" /> Montage terminé</span>
        <h2 className="mt-4 text-3xl font-bold sm:text-4xl">{st.name || 'Ton montage'}</h2>
        <p className="mt-2 text-sm uppercase tracking-[0.16em] text-primary-300">{MONTAGE_LABELS[st.montage as MontageId] || ''}{st.invented ? ' · style inventé' : ''}</p>
        {st.reason && <p className="mt-4 text-dark-300">Pourquoi ce style : {st.reason}.</p>}
        {pal && (
          <div className="mt-5 flex gap-2">
            {[pal.dark, pal.dark2, pal.accent, pal.accent2, pal.light].map((c: string) => <span key={c} className="h-8 w-8 rounded-lg ring-1 ring-white/15" style={{ background: c }} />)}
          </div>
        )}
        <dl className="mt-6 grid max-w-md grid-cols-3 gap-3 text-center">
          {[['Durée', fmt(result?.duration)], ['Source', fmt(result?.source_duration)], ['Animations', String(plan.length)]].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <dt className="text-[11px] uppercase tracking-wider text-dark-400">{k}</dt><dd className="mt-1 font-display text-lg font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
        {plan.length > 0 && (
          <div className="mt-6 flex h-3 max-w-md overflow-hidden rounded-full bg-white/5">
            {plan.map((p, i) => <span key={i} className={p.layout === 'full' ? 'bg-accent-400' : 'bg-primary-400'} style={{ flex: 1, marginRight: 2 }} title={p.type} />)}
          </div>
        )}
        <div className="mt-8 flex flex-wrap gap-3">
          <button className="btn-accent inline-flex items-center gap-2" onClick={() => downloadJobResult(jobId)}><Download className="h-4 w-4" /> Télécharger le MP4</button>
          <button className="btn-secondary inline-flex items-center gap-2" onClick={onAgain}><RefreshCw className="h-4 w-4" /> Remonter avec un autre style</button>
        </div>
      </div>
    </div>
  )
}

/* ================================================================== PAGE */
export default function Studio() {
  const { videoId: routeVideo } = useParams()
  const navigate = useNavigate()
  const [video, setVideo] = useState<VideoItem | null>(null)
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [styles, setStyles] = useState<StudioStyle[]>([])
  const [recent, setRecent] = useState<RecentStyle[]>([])
  const [choice, setChoice] = useState<Choice>('auto')
  const [filter, setFilter] = useState<MontageId | 'all'>('all')
  const [logoAsset, setLogoAsset] = useState<string | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [brand, setBrand] = useState('')
  const [vocab, setVocab] = useState('')
  const [color, setColor] = useState<string>('')
  const [density, setDensity] = useState<Density>('medium')
  const [captions, setCaptions] = useState(true)
  const [music, setMusic] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)
  const { upload, uploading, progress: upPct } = useVideoUpload()
  const { job } = useJobPolling(jobId, 2500)
  const fileRef = useRef<HTMLInputElement>(null)
  const logoRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listStudioStyles().then((r) => {
      setStyles(r.styles); setRecent(r.recent)
      if (r.logo_asset) { setLogoAsset(r.logo_asset); setLogoPreview(logoUrl(r.logo_asset)) }
    }).catch(() => {})
    listVideos(0, 12).then((r) => setVideos((Array.isArray(r) ? r : r?.items || []) as VideoItem[])).catch(() => {})
  }, [])
  useEffect(() => {
    if (routeVideo) getVideo(routeVideo).then(setVideo).catch(() => toast('error', 'Vidéo introuvable'))
  }, [routeVideo])

  const recentIds = useMemo(() => new Set(recent.slice(0, 6).map((r) => r.id)), [recent])
  const montages = useMemo(() => Array.from(new Set(styles.map((s) => s.montage))), [styles])
  const shown = styles.filter((s) => filter === 'all' || s.montage === filter)

  const onFile = useCallback(async (f?: File | null) => {
    if (!f) return
    try {
      validateVideoFile(f)
      const v = await upload(f)
      setVideo(v)
      navigate(`/studio/${v.id}`, { replace: true })
      toast('success', 'Vidéo importée')
    } catch (e) {
      toast('error', getErrorMessage(e, 'Import impossible'))
    }
  }, [upload, navigate])

  const onLogo = useCallback(async (f?: File | null) => {
    if (!f) return
    try {
      setLogoPreview(URL.createObjectURL(f))
      const id = await uploadLogo(f)
      setLogoAsset(id)
      toast('success', 'Logo prêt — il sera détouré et posé sur la vidéo')
    } catch (e) {
      setLogoPreview(null)
      toast('error', getErrorMessage(e, 'Logo refusé'))
    }
  }, [])

  const launch = async () => {
    if (!video) return
    setLaunching(true)
    try {
      const j = await createJob({
        video_id: video.id, job_type: 'pipeline', mode: 'studio_facecam', pipeline_version: 'v2',
        options: {
          studio_style: choice, motion_density: density, dynamic_captions: captions, music,
          ...(logoAsset ? { logo_asset: logoAsset } : {}),
          ...(brand.trim() ? { brand_name: brand.trim() } : {}),
          ...(vocab.trim() ? { vocabulary: vocab.trim() } : {}),
          ...(/^#[0-9a-fA-F]{6}$/.test(color) ? { brand_color: color } : {}),
        } as any,
      })
      setJobId(j.id)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      toast('error', getErrorMessage(e, 'Lancement impossible'))
    } finally {
      setLaunching(false)
    }
  }

  const done = job?.status === 'completed'
  const failed = job?.status === 'failed' || job?.status === 'cancelled'

  return (
    <div className="relative mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6 lg:px-8">
      <Hero />

      <AnimatePresence mode="wait">
        {jobId && !failed ? (
          <motion.section key="run" {...fadeUp} className="mt-8 rounded-[24px] border border-white/[0.07] bg-dark-900/50 p-5 sm:p-10">
            {done
              ? <Result jobId={jobId} result={job?.result || {}} onAgain={() => { setJobId(null); setChoice('auto') }} />
              : <RenderProgress progress={job?.progress ?? 0} status={job?.status || 'pending'} error={job?.error_message}
                  onCancel={async () => { try { await cancelJob(jobId) } catch { /* noop */ } setJobId(null) }} />}
          </motion.section>
        ) : (
          <motion.div key="setup" {...fadeUp} className="mt-8 space-y-6">
            {failed && job?.error_message && (
              <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">Le montage a échoué : {job.error_message}</div>
            )}

            {/* 1. vidéo */}
            <Step n={1} title="Ta vidéo face caméra" hint="MP4 ou MOV, vertical ou horizontal — les hésitations et silences seront coupés." done={!!video}>
              {video ? (
                <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.05] p-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-400/15"><Film className="h-6 w-6 text-emerald-300" /></div>
                  <div className="min-w-0 flex-1"><div className="truncate font-semibold">{video.title}</div><div className="text-sm text-dark-400">{fmt(video.duration_s)}</div></div>
                  <button className="btn-secondary text-sm" onClick={() => { setVideo(null); navigate('/studio', { replace: true }) }}><X className="mr-1 inline h-4 w-4" />Changer</button>
                </div>
              ) : (
                <>
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => { e.preventDefault(); onFile(e.dataTransfer.files?.[0]) }}
                    onClick={() => !uploading && fileRef.current?.click()}
                    className="studio-dropzone flex cursor-pointer flex-col items-center justify-center px-6 py-14 text-center"
                  >
                    <input ref={fileRef} type="file" accept="video/*" hidden onChange={(e) => onFile(e.target.files?.[0])} />
                    {uploading ? (
                      <>
                        <Loader2 className="h-10 w-10 animate-spin text-primary-300" />
                        <div className="mt-4 font-semibold">Import… {upPct}%</div>
                        <div className="mt-3 h-1.5 w-64 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-gradient-to-r from-primary-400 to-accent-400 transition-all" style={{ width: `${upPct}%` }} /></div>
                      </>
                    ) : (
                      <>
                        <motion.div animate={{ y: [0, -6, 0] }} transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
                          className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-500/15"><Upload className="h-7 w-7 text-primary-200" /></motion.div>
                        <div className="mt-5 text-lg font-semibold">Dépose ta vidéo ici</div>
                        <div className="mt-1 text-sm text-dark-400">ou clique pour la choisir</div>
                      </>
                    )}
                  </div>
                  {videos.length > 0 && (
                    <div className="mt-6">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-dark-400">Ou reprends une vidéo déjà importée</div>
                      <div className="no-scrollbar flex gap-3 overflow-x-auto pb-1">
                        {videos.map((v) => (
                          <button key={v.id} onClick={() => { setVideo(v); navigate(`/studio/${v.id}`, { replace: true }) }}
                            className="cf-card shrink-0 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-left">
                            <div className="max-w-[200px] truncate text-sm font-semibold">{v.title}</div>
                            <div className="text-xs text-dark-400">{fmt(v.duration_s)}</div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </Step>

            {/* 2. style */}
            <Step n={2} title="Le style du montage" hint="Chaque style est une façon différente de composer l’image — pas seulement des couleurs." done={!!choice}>
              <div className="grid gap-3 md:grid-cols-2">
                <MagicChoice active={choice === 'auto'} onClick={() => setChoice('auto')} icon={<Sparkles className="h-6 w-6" />}
                  title="Choisi pour ma vidéo (recommandé)"
                  text="Le moteur lit ton discours, choisit le mode de montage le plus adapté et évite ceux de tes derniers montages." />
                <MagicChoice active={choice === 'invent'} onClick={() => setChoice('invent')} icon={<Shuffle className="h-6 w-6" />}
                  title="Invente un style jamais vu"
                  text="Nouvelle combinaison de mise en page, typographie, transitions, sous-titres et palette, créée pour cette vidéo." />
              </div>
              <div className="mt-8 flex flex-wrap items-center gap-2">
                <span className="mr-1 text-xs font-semibold uppercase tracking-[0.14em] text-dark-400">Ou choisis toi-même</span>
                {(['all', ...montages] as (MontageId | 'all')[]).map((m) => (
                  <button key={m} onClick={() => setFilter(m)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${filter === m ? 'border-primary-400/60 bg-primary-500/15 text-white' : 'border-white/10 text-dark-300 hover:text-white'}`}>
                    {m === 'all' ? 'Tous' : MONTAGE_LABELS[m]}
                  </button>
                ))}
              </div>
              <motion.div layout className="mt-5 grid grid-cols-2 gap-3 sm:gap-4 sm:grid-cols-3 lg:grid-cols-5">
                <AnimatePresence>
                  {shown.map((s, i) => (
                    <motion.div key={s.id} className="min-w-0" layout initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ delay: i * 0.03, duration: 0.45, ease }}>
                      <StyleCard style={s} selected={choice === s.id} recent={recentIds.has(s.id)} onClick={() => setChoice(s.id)} />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </motion.div>
            </Step>

            {/* 3. marque */}
            <Step n={3} title="Ta marque" hint="Le logo est détouré proprement (jamais coupé) et apparaît sur toute la vidéo et sur la carte de fin." done={!!logoAsset}>
              <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
                <button type="button" onClick={() => logoRef.current?.click()}
                  className="group relative flex aspect-square items-center justify-center overflow-hidden rounded-2xl border border-dashed border-white/15 bg-[conic-gradient(#1a1b22_25%,#23242d_0_50%,#1a1b22_0_75%,#23242d_0)] bg-[length:22px_22px]">
                  <input ref={logoRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => onLogo(e.target.files?.[0])} />
                  {logoPreview ? <img src={logoPreview} alt="Logo" className="max-h-[70%] max-w-[80%] object-contain drop-shadow-xl" /> : (
                    <div className="text-center text-dark-300"><ImagePlus className="mx-auto h-8 w-8" /><div className="mt-2 text-sm font-medium">Ajouter le logo</div><div className="text-xs text-dark-500">PNG, JPG, WEBP</div></div>
                  )}
                  {logoPreview && <span className="absolute bottom-3 rounded-full bg-black/60 px-3 py-1 text-xs opacity-0 transition-opacity group-hover:opacity-100">Remplacer</span>}
                </button>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium">Nom de la marque</span>
                    <input className="input-field" placeholder="ex. FINAB" value={brand} maxLength={60} onChange={(e) => setBrand(e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium">Couleur de marque <span className="text-dark-500">(optionnel)</span></span>
                    <div className="flex gap-2">
                      <input type="color" value={color || '#3f72ff'} onChange={(e) => setColor(e.target.value)} className="h-[42px] w-14 cursor-pointer rounded-lg border border-dark-600 bg-dark-800" />
                      <input className="input-field" placeholder="le style décide" value={color} onChange={(e) => setColor(e.target.value)} />
                    </div>
                  </label>
                  <label className="block sm:col-span-2">
                    <span className="mb-1.5 block text-sm font-medium">Mots importants <span className="text-dark-500">(aide la transcription à les écrire juste)</span></span>
                    <input className="input-field" placeholder="ex. demandeur d'asile, Canada, rendez-vous" value={vocab} maxLength={300} onChange={(e) => setVocab(e.target.value)} />
                  </label>
                  <div className="sm:col-span-2">
                    <span className="mb-2 block text-sm font-medium">Quantité de motion design</span>
                    <div className="grid grid-cols-3 gap-1 rounded-xl border border-white/10 bg-dark-800/60 p-1">
                      {([['light', 'Léger'], ['medium', 'Équilibré'], ['heavy', 'Intense']] as [Density, string][]).map(([v, l]) => (
                        <button key={v} onClick={() => setDensity(v)} className={`relative rounded-lg py-2 text-sm font-medium ${density === v ? 'text-white' : 'text-dark-400 hover:text-white'}`}>
                          {density === v && <motion.span layoutId="dens" className="absolute inset-0 rounded-lg bg-primary-500/25 ring-1 ring-primary-400/40" transition={{ duration: 0.4, ease }} />}
                          <span className="relative">{l}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 sm:col-span-2">
                    {[[captions, setCaptions, 'Sous-titres karaoké', Subtitles], [music, setMusic, 'Musique de fond', Music2]].map(([on, set, label, Icon]: any) => (
                      <button key={label} onClick={() => set(!on)} className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors ${on ? 'border-primary-400/50 bg-primary-500/10 text-white' : 'border-white/10 text-dark-400'}`}>
                        <Icon className="h-4 w-4" /> {label}
                        <span className={`ml-1 h-4 w-7 rounded-full p-0.5 transition-colors ${on ? 'bg-primary-500' : 'bg-white/15'}`}><span className={`block h-3 w-3 rounded-full bg-white transition-transform ${on ? 'translate-x-3' : ''}`} /></span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Step>

            {/* lancement */}
            <motion.div {...fadeUp} className="sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-dark-900/85 p-4 shadow-card-premium backdrop-blur-xl sm:p-5">
              <div className="text-sm text-dark-300">
                {video ? <>Prêt : <b className="text-white">{video.title}</b> · {choice === 'auto' ? 'style choisi pour la vidéo' : choice === 'invent' ? 'style inventé' : styles.find((s) => s.id === choice)?.name}</> : 'Importe d’abord ta vidéo.'}
              </div>
              <button disabled={!video || launching} onClick={launch} className="btn-accent inline-flex items-center gap-2 px-7 py-3 text-base disabled:cursor-not-allowed disabled:opacity-40">
                {launching ? <Loader2 className="h-5 w-5 animate-spin" /> : <Wand2 className="h-5 w-5" />} Lancer le montage <ArrowRight className="h-4 w-4" />
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
