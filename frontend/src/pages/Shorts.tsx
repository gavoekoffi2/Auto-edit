import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowDown, ArrowRight, ArrowUp, BookOpen, Check, Download, Film, Layers, Loader2, Music2, RefreshCw,
  Scissors, Smartphone, Sparkles, Subtitles, Upload, Wand2, X,
} from 'lucide-react'
import { cancelJob, createJob, downloadJobResult, getJobDownloadUrl } from '../api/jobs'
import { listVideos, validateVideoFile } from '../api/videos'
import { useVideoUpload } from '../hooks/useVideoUpload'
import { useJobPolling } from '../hooks/useJobPolling'
import { getErrorMessage } from '../api/client'
import { toast } from '../components/ui/Toast'
import '../styles/studio.css'

interface VideoItem { id: string; title: string; duration_s: number | null }
type Theme = 'auto' | 'or_noir' | 'braise' | 'ocean' | 'menthe' | 'royal'
type Layout = 'auto' | 'cadre' | 'plein'

const MAX_RUSHES = 10
const ease = [0.16, 1, 0.3, 1] as const
const fadeUp = { initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -12 }, transition: { duration: 0.6, ease } }

const THEMES: { id: Exclude<Theme, 'auto'>; name: string; a: string; b: string; bg: string }[] = [
  { id: 'or_noir', name: 'Noir & or', a: '#FFC93C', b: '#F5A300', bg: '#0A0A0D' },
  { id: 'braise', name: 'Braise', a: '#FF7A1A', b: '#E2361B', bg: '#140804' },
  { id: 'ocean', name: 'Océan', a: '#33D6FF', b: '#1E8BFF', bg: '#03111F' },
  { id: 'menthe', name: 'Menthe', a: '#4BE3A1', b: '#12B886', bg: '#04140D' },
  { id: 'royal', name: 'Royal', a: '#FFD25A', b: '#A05AFF', bg: '#1A0B2E' },
]

const STEPS: { at: number; label: string; hint: string }[] = [
  { at: 0, label: 'Transcription des rushes', hint: 'Chaque mot de chaque rush est minuté' },
  { at: 24, label: 'Tri des prises', hint: 'Meilleure prise gardée, faux départs coupés' },
  { at: 30, label: 'Construction du récit', hint: 'Les rushes remis dans un ordre cohérent' },
  { at: 34, label: 'Assemblage 9:16', hint: 'Silences coupés, cadrage centré sur le visage' },
  { at: 49, label: 'Motion design', hint: 'Chapitres, sous-titres, cartes, versets' },
  { at: 89, label: 'Son', hint: 'Voix nettoyée, effets sonores, musique' },
  { at: 95, label: 'Export', hint: 'MP4 prêt à poster sur TikTok' },
]

function fmt(s: number | null | undefined) {
  if (!s && s !== 0) return '—'
  const m = Math.floor(s / 60), r = Math.round(s % 60)
  return m ? `${m} min ${String(r).padStart(2, '0')}` : `${r} s`
}

function Hero() {
  return (
    <div className="relative overflow-hidden rounded-[28px] border border-white/[0.07] bg-dark-900/60 px-6 py-10 sm:px-10 sm:py-14">
      <div className="studio-orbit left-[-10%] top-[-40%] h-72 w-72" style={{ background: '#F5A300' }} />
      <div className="absolute inset-0 cf-grid-dots opacity-60" />
      <div className="relative grid items-center gap-10 lg:grid-cols-[1.2fr_1fr]">
        <div>
          <div className="flex flex-wrap gap-2">
            <Link to="/studio" className="rounded-full border border-white/10 px-3 py-1 text-xs font-semibold text-dark-300 hover:text-white">Studio · une vidéo</Link>
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/40 bg-amber-300/10 px-3 py-1 text-xs font-semibold text-amber-200">
              <Smartphone className="h-3.5 w-3.5" /> Shorts TikTok · plusieurs rushes
            </span>
          </div>
          <h1 className="mt-5 text-4xl font-bold leading-[1.05] sm:text-5xl text-balance">
            Envoie tes rushes bruts. Reçois une vidéo <span className="text-amber-300">prête à poster</span>.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-dark-300 sm:text-lg">
            Filmé en plusieurs fois, dans le désordre, avec des reprises ? Le moteur garde la meilleure prise, coupe les silences,
            les répétitions et les faux départs, remet ton discours dans l’ordre, puis l’habille : chapitres, sous-titres mot à mot,
            cartes animées, versets, effets sonores et musique.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[[Layers, 'Plusieurs rushes', 'remis dans un ordre cohérent'], [Scissors, 'Nettoyage complet', 'silences, reprises, hésitations'],
            [Sparkles, 'Motion design', 'cartes calées sur ta voix'], [BookOpen, 'Versets exacts', 'Louis Segond 1910']].map(([Icon, t, h]: any) => (
            <div key={t} className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <Icon className="h-5 w-5 text-amber-300" />
              <div className="mt-3 font-semibold">{t}</div>
              <div className="text-xs text-dark-400">{h}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Step({ n, title, hint, done, children }: { n: number; title: string; hint?: string; done?: boolean; children: React.ReactNode }) {
  return (
    <motion.section {...fadeUp} className="rounded-[24px] border border-white/[0.07] bg-dark-900/50 p-5 sm:p-8">
      <header className="mb-6 flex items-start gap-4">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${done ? 'bg-emerald-400/15 text-emerald-300' : 'bg-amber-300/15 text-amber-200'}`}>
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

function Progress({ progress, status, error, onCancel }: { progress: number; status: string; error?: string | null; onCancel: () => void }) {
  const active = STEPS.reduce((k, s, i) => (progress >= s.at ? i : k), 0)
  return (
    <div className="grid items-center gap-10 lg:grid-cols-[220px_1fr]">
      <div className="text-center">
        <div className="font-display text-6xl font-bold tabular-nums">{Math.round(progress)}<span className="text-2xl text-dark-400">%</span></div>
        <div className="mt-1 text-xs uppercase tracking-[0.18em] text-dark-400">{status === 'pending' ? 'en file' : 'en montage'}</div>
        <div className="mx-auto mt-5 h-1.5 w-48 overflow-hidden rounded-full bg-white/10">
          <div className="h-full bg-gradient-to-r from-amber-300 to-orange-500 transition-all" style={{ width: `${Math.max(2, progress)}%` }} />
        </div>
      </div>
      <div>
        <ol className="space-y-2">
          {STEPS.map((s, i) => {
            const st = i < active ? 'done' : i === active ? 'now' : 'todo'
            return (
              <li key={s.label} className={`flex items-center gap-4 rounded-xl border px-4 py-3 ${st === 'now' ? 'border-amber-300/40 bg-amber-300/[0.06]' : 'border-white/[0.05] bg-white/[0.015]'}`}>
                <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${st === 'done' ? 'bg-emerald-400/15 text-emerald-300' : st === 'now' ? 'bg-amber-300 text-black' : 'bg-white/5 text-dark-500'}`}>
                  {st === 'done' ? <Check className="h-4 w-4" /> : st === 'now' ? <Loader2 className="h-4 w-4 animate-spin" /> : i + 1}
                </span>
                <div className="min-w-0">
                  <div className={`text-sm font-semibold ${st === 'todo' ? 'text-dark-500' : ''}`}>{s.label}</div>
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

function Result({ jobId, result, onAgain }: { jobId: string; result: Record<string, any>; onAgain: () => void }) {
  const sh = result?.shorts || {}
  const theme = THEMES.find((t) => t.id === sh.theme)
  const chapters: { t: number; title: string }[] = sh.chapters || []
  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,360px)_1fr]">
      <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.9, ease }}
        className="mx-auto w-full max-w-[340px] rounded-[42px] border-[10px] border-[#0d0d10] bg-black shadow-card-premium">
        <video src={getJobDownloadUrl(jobId)} controls playsInline className="aspect-[9/16] w-full rounded-[32px] bg-black" />
      </motion.div>
      <div className="flex flex-col justify-center">
        <span className="status-pill w-fit" data-tone="ok"><Check className="h-3.5 w-3.5" /> Vidéo prête à poster</span>
        <h2 className="mt-4 text-3xl font-bold sm:text-4xl">{sh.tag || 'Ton short'}</h2>
        <p className="mt-2 text-sm uppercase tracking-[0.16em] text-amber-300">
          {theme?.name || ''}{sh.layout ? ` · ${sh.layout === 'cadre' ? 'fenêtre 4:5' : 'plein écran'}` : ''}
        </p>
        <dl className="mt-6 grid max-w-lg grid-cols-4 gap-3 text-center">
          {[['Durée', fmt(result?.duration)], ['Rushes', fmt(result?.source_duration)], ['Fichiers', String(sh.rushes ?? '—')], ['Animations', String((sh.cards || []).length)]].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <dt className="text-[11px] uppercase tracking-wider text-dark-400">{k}</dt><dd className="mt-1 font-display text-base font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
        {chapters.length > 0 && (
          <ol className="mt-6 max-w-lg space-y-1.5 text-sm">
            {chapters.map((c) => (
              <li key={c.t} className="flex gap-3"><span className="w-12 shrink-0 tabular-nums text-dark-400">{fmt(c.t)}</span><span>{c.title}</span></li>
            ))}
          </ol>
        )}
        <div className="mt-8 flex flex-wrap gap-3">
          <button className="btn-accent inline-flex items-center gap-2" onClick={() => downloadJobResult(jobId)}><Download className="h-4 w-4" /> Télécharger le MP4</button>
          <button className="btn-secondary inline-flex items-center gap-2" onClick={onAgain}><RefreshCw className="h-4 w-4" /> Nouveau montage</button>
        </div>
      </div>
    </div>
  )
}

export default function Shorts() {
  const [rushes, setRushes] = useState<VideoItem[]>([])
  const [library, setLibrary] = useState<VideoItem[]>([])
  const [queue, setQueue] = useState<string[]>([])
  const [theme, setTheme] = useState<Theme>('auto')
  const [layout, setLayout] = useState<Layout>('auto')
  const [vocab, setVocab] = useState('')
  const [captions, setCaptions] = useState(true)
  const [music, setMusic] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)
  const { upload, uploading, progress: upPct } = useVideoUpload()
  const { job } = useJobPolling(jobId, 2500)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listVideos(0, 20).then((r) => setLibrary((Array.isArray(r) ? r : r?.items || []) as VideoItem[])).catch(() => {})
  }, [])

  const onFiles = useCallback(async (files: FileList | File[] | null) => {
    const list = Array.from(files || []).slice(0, MAX_RUSHES - rushes.length)
    if (!list.length) return
    for (const f of list) {
      try { validateVideoFile(f) } catch (e) { toast('error', getErrorMessage(e, `${f.name} refusé`)); return }
    }
    setQueue(list.map((f) => f.name))
    for (const f of list) {
      try {
        const v = await upload(f)
        setRushes((r) => (r.some((x) => x.id === v.id) ? r : [...r, v]))
      } catch (e) {
        toast('error', getErrorMessage(e, `Import de ${f.name} impossible`))
      } finally {
        setQueue((q) => q.slice(1))
      }
    }
  }, [upload, rushes.length])

  const toggle = (v: VideoItem) => setRushes((r) => (r.some((x) => x.id === v.id) ? r.filter((x) => x.id !== v.id) : r.length < MAX_RUSHES ? [...r, v] : r))
  const move = (i: number, d: -1 | 1) => setRushes((r) => {
    const j = i + d; if (j < 0 || j >= r.length) return r
    const n = [...r]; [n[i], n[j]] = [n[j], n[i]]; return n
  })
  const total = rushes.reduce((s, v) => s + (v.duration_s || 0), 0)

  const launch = async () => {
    if (!rushes.length) return
    setLaunching(true)
    try {
      const j = await createJob({
        video_id: rushes[0].id, extra_video_ids: rushes.slice(1).map((v) => v.id),
        job_type: 'pipeline', mode: 'shorts_facecam', pipeline_version: 'v2',
        options: { shorts_theme: theme, shorts_layout: layout, dynamic_captions: captions, music, ...(vocab.trim() ? { vocabulary: vocab.trim() } : {}) },
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
              ? <Result jobId={jobId} result={job?.result || {}} onAgain={() => { setJobId(null); setRushes([]) }} />
              : <Progress progress={job?.progress ?? 0} status={job?.status || 'pending'} error={job?.error_message}
                  onCancel={async () => { try { await cancelJob(jobId) } catch { /* noop */ } setJobId(null) }} />}
          </motion.section>
        ) : (
          <motion.div key="setup" {...fadeUp} className="mt-8 space-y-6">
            {failed && job?.error_message && (
              <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">Le montage a échoué : {job.error_message}</div>
            )}

            <Step n={1} title="Tes rushes" hint={`1 à ${MAX_RUSHES} fichiers, horizontaux ou verticaux. L’ordre n’a pas d’importance : le moteur remet le discours en ordre.`} done={rushes.length > 0}>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); onFiles(e.dataTransfer.files) }}
                onClick={() => !uploading && fileRef.current?.click()}
                className="studio-dropzone flex cursor-pointer flex-col items-center justify-center px-6 py-12 text-center"
              >
                <input ref={fileRef} type="file" accept="video/*" multiple hidden onChange={(e) => { onFiles(e.target.files); e.target.value = '' }} />
                {uploading ? (
                  <>
                    <Loader2 className="h-10 w-10 animate-spin text-amber-300" />
                    <div className="mt-4 font-semibold">Import de {queue[0] || 'la vidéo'}… {upPct}%</div>
                    {queue.length > 1 && <div className="mt-1 text-sm text-dark-400">encore {queue.length - 1} fichier(s) après</div>}
                    <div className="mt-3 h-1.5 w-64 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-gradient-to-r from-amber-300 to-orange-500 transition-all" style={{ width: `${upPct}%` }} /></div>
                  </>
                ) : (
                  <>
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-300/15"><Upload className="h-7 w-7 text-amber-200" /></div>
                    <div className="mt-5 text-lg font-semibold">Dépose tous tes rushes ici</div>
                    <div className="mt-1 text-sm text-dark-400">ou clique pour en choisir plusieurs</div>
                  </>
                )}
              </div>

              {rushes.length > 0 && (
                <ol className="mt-5 space-y-2">
                  {rushes.map((v, i) => (
                    <li key={v.id} className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-300/15 text-sm font-bold text-amber-200">{String.fromCharCode(65 + i)}</span>
                      <Film className="h-4 w-4 text-dark-400" />
                      <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{v.title}</div><div className="text-xs text-dark-400">{fmt(v.duration_s)}</div></div>
                      <button aria-label="Monter" onClick={() => move(i, -1)} disabled={i === 0} className="rounded-lg p-1.5 text-dark-400 hover:text-white disabled:opacity-30"><ArrowUp className="h-4 w-4" /></button>
                      <button aria-label="Descendre" onClick={() => move(i, 1)} disabled={i === rushes.length - 1} className="rounded-lg p-1.5 text-dark-400 hover:text-white disabled:opacity-30"><ArrowDown className="h-4 w-4" /></button>
                      <button aria-label="Retirer" onClick={() => toggle(v)} className="rounded-lg p-1.5 text-dark-400 hover:text-red-300"><X className="h-4 w-4" /></button>
                    </li>
                  ))}
                  <li className="px-1 text-xs text-dark-400">Total : {fmt(total)} de rushes</li>
                </ol>
              )}

              {library.length > 0 && (
                <div className="mt-6">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-dark-400">Ou ajoute des vidéos déjà importées</div>
                  <div className="no-scrollbar flex gap-3 overflow-x-auto pb-1">
                    {library.map((v) => {
                      const on = rushes.some((x) => x.id === v.id)
                      return (
                        <button key={v.id} onClick={() => toggle(v)}
                          className={`shrink-0 rounded-xl border px-4 py-3 text-left transition-colors ${on ? 'border-amber-300/60 bg-amber-300/10' : 'border-white/[0.07] bg-white/[0.02] hover:border-white/20'}`}>
                          <div className="flex max-w-[220px] items-center gap-2 truncate text-sm font-semibold">{on && <Check className="h-3.5 w-3.5 text-amber-300" />}{v.title}</div>
                          <div className="text-xs text-dark-400">{fmt(v.duration_s)}</div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </Step>

            <Step n={2} title="L’habillage" hint="Laisse le moteur choisir selon le ton de ta vidéo, ou impose un thème." done>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <button onClick={() => setTheme('auto')} data-selected={theme === 'auto'}
                  className={`rounded-2xl border p-4 text-left ${theme === 'auto' ? 'border-amber-300/60 bg-amber-300/10' : 'border-white/[0.08] bg-dark-900'}`}>
                  <Sparkles className="h-6 w-6 text-amber-300" />
                  <div className="mt-3 text-sm font-semibold">Auto</div><div className="text-xs text-dark-400">selon le sujet</div>
                </button>
                {THEMES.map((t) => (
                  <button key={t.id} onClick={() => setTheme(t.id)}
                    className={`rounded-2xl border p-2.5 text-left ${theme === t.id ? 'border-amber-300/60 bg-amber-300/10' : 'border-white/[0.08] bg-dark-900'}`}>
                    <div className="flex h-16 flex-col items-center justify-center gap-1.5 rounded-xl" style={{ background: t.bg }}>
                      <span className="rounded-full px-2 py-0.5 text-[9px] font-extrabold uppercase" style={{ background: t.a, color: t.bg }}>Chapitre</span>
                      <span className="text-[11px] font-black uppercase text-white">Mot <span style={{ color: t.a }}>clé</span></span>
                    </div>
                    <div className="mt-2 px-1 text-sm font-semibold">{t.name}</div>
                  </button>
                ))}
              </div>
              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <div>
                  <span className="mb-2 block text-sm font-medium">Cadrage</span>
                  <div className="grid grid-cols-3 gap-1 rounded-xl border border-white/10 bg-dark-800/60 p-1">
                    {([['auto', 'Auto'], ['cadre', 'Fenêtre 4:5'], ['plein', 'Plein écran']] as [Layout, string][]).map(([v, l]) => (
                      <button key={v} onClick={() => setLayout(v)} className={`rounded-lg py-2 text-sm font-medium ${layout === v ? 'bg-amber-300/20 text-white ring-1 ring-amber-300/40' : 'text-dark-400 hover:text-white'}`}>{l}</button>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-dark-500">Fenêtre 4:5 : idéal pour les vidéos filmées à l’horizontale (bandeau titre en haut, sous-titres en bas).</p>
                </div>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium">Mots importants <span className="text-dark-500">(noms propres, termes techniques)</span></span>
                  <input className="input-field" placeholder="ex. Saint-Esprit, apostasie, Hébreux" value={vocab} maxLength={300} onChange={(e) => setVocab(e.target.value)} />
                </label>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                {[[captions, setCaptions, 'Sous-titres mot à mot', Subtitles], [music, setMusic, 'Musique de fond', Music2]].map(([on, set, label, Icon]: any) => (
                  <button key={label} onClick={() => set(!on)} className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium ${on ? 'border-amber-300/50 bg-amber-300/10 text-white' : 'border-white/10 text-dark-400'}`}>
                    <Icon className="h-4 w-4" /> {label}
                    <span className={`ml-1 h-4 w-7 rounded-full p-0.5 ${on ? 'bg-amber-400' : 'bg-white/15'}`}><span className={`block h-3 w-3 rounded-full bg-white transition-transform ${on ? 'translate-x-3' : ''}`} /></span>
                  </button>
                ))}
              </div>
            </Step>

            <motion.div {...fadeUp} className="sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-dark-900/85 p-4 shadow-card-premium backdrop-blur-xl sm:p-5">
              <div className="text-sm text-dark-300">
                {rushes.length ? <>Prêt : <b className="text-white">{rushes.length} rush{rushes.length > 1 ? 'es' : ''}</b> · {fmt(total)}</> : 'Importe d’abord tes rushes.'}
              </div>
              <button disabled={!rushes.length || launching || uploading} onClick={launch} className="btn-accent inline-flex items-center gap-2 px-7 py-3 text-base disabled:cursor-not-allowed disabled:opacity-40">
                {launching ? <Loader2 className="h-5 w-5 animate-spin" /> : <Wand2 className="h-5 w-5" />} Monter mon short <ArrowRight className="h-4 w-4" />
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
