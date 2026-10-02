import { useEffect, useRef, useState, useCallback } from 'react'
import {
  Clapperboard, Send, Loader2, Sparkles, Download, Trash2, RotateCcw, Wand2, X, Film, ImagePlus, Check,
} from 'lucide-react'
import {
  getAdCatalog, interviewTurn, previewScript, createAd, listAds, getAd, cancelAd, deleteAd,
  adVideoUrl, adThumbUrl, type AdProject, type AdTemplate, type AdMontage, type AdFormat, type Storyboard,
} from '../api/ads'
import { uploadLogo } from '../api/studio'
import { toast } from '../components/ui/Toast'
import { getErrorMessage } from '../api/client'

type Msg = { role: 'assistant' | 'user'; content: string }

const SCENE_LABELS: Record<string, string> = {
  title_slam: 'Titre choc', icon_cards: 'Cartes icônes', checklist: 'Avantages cochés', loss_drain: 'Argent aspiré',
  hero_reveal: 'Révélation 3D', split_compare: 'Écran partagé', bars_compare: 'Barres comparées', crowd_select: 'Foule / exclusivité',
  toggle_decision: 'Décision ON', choice_cards: 'Choix du profil', timer_ring: 'Minuteur', cta_button: 'Bouton d’action',
  chat_bubbles: 'Conversation', stat_number: 'Chiffre clé', end_card: 'Carte de fin', continue: '↳ suite',
  hook_question: 'Accroche choc', pain_stack: 'Douleurs barrées', counter_rows: 'Compteurs', versus: 'Avant / après',
  rival_split: 'Vous vs concurrent', punch: 'Coup de poing', pivot: 'Bascule', product_reveal: 'Révélation produit',
  tiles: 'Catalogue', phone_checks: 'Téléphone + coches', pillars: '3 piliers', phone_ring: 'Téléphone qui sonne',
  price_offer: 'Prix / offre', cta: 'Appel à l’action', title: 'Titre choc',
  st_stat: 'Constat géant', st_laptop: 'Démo ordinateur', st_grid: 'Grille', st_figure: 'Silhouette', st_dark: 'Rupture noire',
  st_pattern: 'Rupture rouge', st_product: 'Coffret produit', st_chess: 'Stratégie', st_stage: 'Scène', st_checklist: 'Liste cochée',
  st_shield: 'Bouclier', st_bonus: 'Bonus', st_scarcity: 'Rareté', st_offer: 'Prix', st_cta: 'Appel à l’action', st_words: 'Texte',
  ds_count: 'Foule', ds_timer: 'Compte à rebours', ds_envelope: 'Enveloppe REFUSÉ', ds_reveal: 'Monde rouge', ds_folders: 'Dossiers',
  ds_book: 'Livre ouvert', ds_bonus: 'Bonus', ds_imagine: '« Imagine… »', ds_proof: 'Preuves', ds_offer: 'Prix', ds_cta: 'Enveloppe VALIDÉ', ds_title: 'Texte',
  ap_hook: 'Pilule 3D', ap_kin: 'Téléphone 3D', ap_pills: 'Pilules', ap_person: 'Personne + bulle', ap_reveal: 'Icône d’appli',
  ap_steps: 'Étapes', ap_trio: 'Trio d’écrans', ap_chips: 'Puces en verre', ap_price: 'Prix', ap_cta: 'Téléchargement', ap_text: 'Texte',
  ls_hero: 'Personne + titre', ls_device: 'Téléphone couché', ls_switch: 'Changements de couleur', ls_punch: 'Coup de poing',
  ls_reveal: 'Révélation', ls_benefits: 'Avantages', ls_price: 'Prix 3D', ls_cta: 'Appel à l’action', ls_text: 'Titres',
  ev_title: 'Mots encadrés', ev_photo: 'Photo + texte', ev_list: 'Étiquettes', ev_punch: 'Coup de poing', ev_reveal: 'Révélation',
  ev_amount: 'Montant géant', ev_date: 'Date', ev_poster: 'Affiche finale',
}

const FORMAT_BOX: Record<string, string> = { '9:16': 'aspect-[9/16]', '4:5': 'aspect-[4/5]', '1:1': 'aspect-square', '16:9': 'aspect-video' }
const fmtOf = (b: Record<string, unknown>) => (typeof b.format === 'string' && FORMAT_BOX[b.format] ? b.format : '9:16')

function FormatCard({ f, active, onClick, disabled }: { f: AdFormat; active: boolean; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`rounded-xl p-2 border text-left transition-colors ${active ? 'border-primary-500 bg-primary-600/10' : 'border-dark-600 hover:border-primary-500'}`}>
      <div className="h-16 flex items-center justify-center">
        <div className={`${FORMAT_BOX[f.id]} h-full max-w-full rounded-md bg-gradient-to-br from-primary-500/70 to-dark-700 border border-white/20`} />
      </div>
      <div className="mt-1 text-[11px] font-semibold">{f.name}</div>
      <div className="text-[10px] text-dark-400 leading-tight">{f.hint}</div>
    </button>
  )
}

// mini-aperçu animé de chaque mode de montage (grammaire, pas couleurs)
function MontageThumb({ id }: { id: string }) {
  const base = 'relative w-full aspect-[9/16] rounded-lg overflow-hidden bg-[#0b0b10] border border-dark-700'
  if (id === 'impact') return (
    <div className={base}>
      <div className="absolute inset-x-2 top-2 h-2 rounded bg-white/90" /><div className="absolute left-4 right-4 top-6 h-2 rounded bg-yellow-400" />
      <div className="absolute left-1/2 -translate-x-1/2 bottom-6 w-7 h-7 bg-yellow-400 rotate-45 animate-pulse" />
      <div className="absolute inset-x-3 bottom-2 h-2 rounded-full bg-dark-600" />
      <div className="absolute right-1 top-12 w-5 h-2 bg-red-500 rotate-6" />
    </div>)
  if (id === 'classique') return (
    <div className={base}>
      <div className="absolute inset-x-3 top-3 h-2 rounded bg-white/80" />
      {[0, 1, 2].map((i) => <div key={i} className="absolute left-3 right-3 h-3 rounded bg-white/15 border border-white/20" style={{ top: 22 + i * 14 }} />)}
      <div className="absolute left-1/2 -translate-x-1/2 bottom-3 w-6 h-7 rounded-b-full bg-amber-400/80" />
    </div>)
  if (id === 'auto') return (
    <div className={`${base} bg-gradient-to-br from-primary-700/60 to-[#0b0b10]`}>
      <Sparkles className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 text-white animate-pulse" />
    </div>)
  const deco: Record<string, JSX.Element> = {
    studio: <div className="absolute inset-0 bg-white"><div className="absolute inset-x-3 top-3 h-2 rounded bg-black/80" /><div className="absolute left-3 right-3 top-9 h-8 rounded-sm bg-dark-800 border-b-2 border-dark-400" /><div className="absolute right-2 bottom-8 px-1 h-2.5 bg-violet-600 -rotate-6" /><div className="absolute inset-x-0 bottom-0 h-6 flex justify-center gap-0.5 items-end">{[0, 1, 2, 3].map((i) => <div key={i} className="w-2.5 h-5 rounded-t-full bg-black" />)}</div></div>,
    dossier: <><div className="absolute inset-x-0 top-0 h-1/2 bg-[#f3f3f5]"><div className="absolute left-1/2 -translate-x-1/2 top-3 w-10 h-6 bg-[#c49a5c] rounded-sm"><div className="absolute left-1 top-1.5 px-0.5 text-[5px] font-black text-red-600 border border-red-600 -rotate-12">REFUSÉ</div></div></div><div className="absolute inset-x-0 bottom-0 h-1/2 bg-[#C8102E]"><div className="absolute left-1/2 -translate-x-1/2 top-2 w-6 h-8 bg-violet-700 rotate-6" /></div></>,
    app: <div className="absolute inset-0 bg-gradient-to-b from-white to-violet-200"><div className="absolute left-1/2 -translate-x-1/2 top-6 w-7 h-14 rounded-md bg-[#0c0c12] -rotate-12 shadow-lg"><div className="m-1 h-3 w-3 rounded-full border-2 border-violet-500" /></div><div className="absolute left-2 top-3 px-1 h-3 rounded bg-violet-600 -rotate-6 text-[5px] text-white font-bold">PILULE</div></div>,
    lifestyle: <div className="absolute inset-0 grid grid-rows-3"><div className="bg-[#1DB954]" /><div className="bg-[#E50914]" /><div className="bg-violet-600" /><div className="absolute left-2 top-3 text-white font-black text-[9px] leading-none">TITRE<br />GÉANT</div><div className="absolute right-1 bottom-1 text-lg">😄</div></div>,
    event: <div className="absolute inset-0 bg-gradient-to-b from-orange-400 to-orange-600"><div className="absolute left-1/2 -translate-x-1/2 top-5 text-[6px] font-bold text-orange-600 bg-white rounded-full px-1">À la clé ?</div><div className="absolute inset-x-0 top-10 text-center text-white font-black text-[10px]">5 M</div><div className="absolute left-1/2 -translate-x-1/2 bottom-5 px-1.5 h-3 rounded bg-[#1F2547] -rotate-3" /></div>,
  }
  return <div className={base}>{deco[id]}</div>
}

function Bubble({ m }: { m: Msg }) {
  const mine = m.role === 'user'
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-relaxed ${mine
        ? 'bg-primary-600 text-white rounded-br-md' : 'bg-dark-800 text-dark-100 rounded-bl-md border border-dark-700'}`}>
        {m.content.split('**').map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : <span key={i}>{part}</span>))}
      </div>
    </div>
  )
}

function AdCard({ ad, onChange }: { ad: AdProject; onChange: () => void }) {
  const [playing, setPlaying] = useState(false)
  const busy = ad.status === 'pending' || ad.status === 'processing'
  return (
    <div className="card p-3 flex gap-3 items-start">
      <div className={`${{ '16:9': 'w-40 h-[90px]', '1:1': 'w-28 h-28', '4:5': 'w-28 h-[140px]' }[(ad.result?.format || ad.brief?.format) as string] || 'w-24 h-40'} shrink-0 rounded-lg overflow-hidden bg-dark-800 flex items-center justify-center`}>
        {ad.status === 'completed'
          ? (playing
            ? <video src={adVideoUrl(ad.id)} className="w-full h-full object-cover" controls autoPlay playsInline />
            : <button onClick={() => setPlaying(true)} className="w-full h-full" aria-label="Lire la pub">
                <img src={adThumbUrl(ad.id)} alt="" className="w-full h-full object-cover" />
              </button>)
          : busy ? <Loader2 className="w-6 h-6 text-primary-400 animate-spin" /> : <Film className="w-6 h-6 text-dark-500" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">{ad.title}</div>
        <div className="text-xs text-dark-400 mb-2">{ad.template} · {String(ad.result?.format || ad.brief?.format || '9:16')} · {new Date(ad.created_at).toLocaleString('fr-FR')}</div>
        {busy && (
          <>
            <div className="text-xs text-dark-300 mb-1">{ad.stage || 'En file d’attente…'} — {ad.progress}%</div>
            <div className="h-1.5 bg-dark-800 rounded-full overflow-hidden mb-2">
              <div className="h-full bg-primary-500 transition-all" style={{ width: `${ad.progress}%` }} />
            </div>
            <button className="text-xs text-dark-400 hover:text-white flex items-center gap-1"
              onClick={async () => { await cancelAd(ad.id); onChange() }}><X className="w-3 h-3" /> Annuler</button>
          </>
        )}
        {ad.status === 'failed' && <div className="text-xs text-red-400 mb-2">{ad.error_message}</div>}
        {ad.status === 'completed' && (
          <div className="flex flex-wrap gap-2 mt-1">
            <a href={adVideoUrl(ad.id)} download className="btn-primary text-xs px-3 py-1.5 flex items-center gap-1">
              <Download className="w-3 h-3" /> Télécharger</a>
            {ad.result?.duration && <span className="text-xs text-dark-400 self-center">{Math.round(ad.result.duration)} s</span>}
          </div>
        )}
        {!busy && (
          <button className="text-xs text-dark-500 hover:text-red-400 mt-2 flex items-center gap-1"
            onClick={async () => { if (confirm('Supprimer cette pub ?')) { await deleteAd(ad.id); onChange() } }}>
            <Trash2 className="w-3 h-3" /> Supprimer</button>
        )}
      </div>
    </div>
  )
}

export default function AdStudio() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [brief, setBrief] = useState<Record<string, unknown>>({})
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [templates, setTemplates] = useState<AdTemplate[]>([])
  const [montages, setMontages] = useState<AdMontage[]>([])
  const [upload, setUpload] = useState(false)
  const [picker, setPicker] = useState(false)
  const [fmtPicker, setFmtPicker] = useState(false)
  const [multiple, setMultiple] = useState(false)
  const [formats, setFormats] = useState<AdFormat[]>([])
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const [board, setBoard] = useState<Storyboard | null>(null)
  const [scripting, setScripting] = useState(false)
  const [creating, setCreating] = useState(false)
  const [ads, setAds] = useState<AdProject[]>([])
  const endRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(() => { listAds().then(setAds).catch(() => {}) }, [])

  const start = useCallback(async () => {
    setMessages([]); setBrief({}); setDone(false); setBoard(null); setThinking(true)
    try {
      const r = await interviewTurn({})
      setMessages([{ role: 'assistant', content: r.reply }]); setBrief(r.brief); setSuggestions(r.suggestions)
      setUpload(!!r.upload); setPicker(!!r.montage_picker); setFmtPicker(!!r.format_picker); setMultiple(!!r.multiple)
    } catch (e) { toast('error', getErrorMessage(e)) } finally { setThinking(false) }
  }, [])

  useEffect(() => { start(); refresh(); getAdCatalog().then((c) => { setTemplates(c.templates); setMontages(c.montages || []); setFormats(c.formats || []) }).catch(() => {}) }, [start, refresh])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, board])

  // suivi des rendus en cours
  useEffect(() => {
    const running = ads.filter((a) => a.status === 'pending' || a.status === 'processing')
    if (!running.length) return
    const t = setInterval(async () => {
      const upd = await Promise.all(running.map((a) => getAd(a.id).catch(() => a)))
      setAds((prev) => prev.map((a) => upd.find((u) => u.id === a.id) || a))
      upd.filter((u) => u.status === 'completed').forEach((u) => toast('success', `« ${u.title} » est prête 🎬`))
    }, 4000)
    return () => clearInterval(t)
  }, [ads])

  const send = async (text: string, display?: string) => {
    const answer = text.trim()
    if (!answer || thinking) return
    if (done && answer === 'Créer ma pub') { await makeScript(); return }
    const history = [...messages, { role: 'user' as const, content: display || answer }]
    setMessages(history); setInput(''); setThinking(true); setSuggestions([]); setUpload(false); setPicker(false); setFmtPicker(false)
    try {
      const r = await interviewTurn(brief, answer, history.map((m) => ({ role: m.role, content: m.content })))
      setBrief(r.brief); setDone(r.done); setSuggestions(r.suggestions); setUpload(!!r.upload); setPicker(!!r.montage_picker)
      setFmtPicker(!!r.format_picker); setMultiple(!!r.multiple)
      setMessages([...history, { role: 'assistant', content: r.reply }])
    } catch (e) { toast('error', getErrorMessage(e)) } finally { setThinking(false) }
  }

  const makeScript = async () => {
    setScripting(true)
    try {
      const r = await previewScript(brief); setBoard(r.storyboard)
      // le montage « automatique » est fixé ici : la vidéo utilisera exactement ce script
      setBrief((prev) => ({ ...prev, montage: r.brief.montage, format: r.brief.format }))
      if (r.montage_choice?.auto) setMessages((m) => [...m, { role: 'assistant', content: `🎬 Montage choisi : **${r.montage_choice!.name}** — ${r.montage_choice!.reason}.` }])
      else if (r.montage_choice && r.montage_choice.reason !== 'choisi par vous') setMessages((m) => [...m, { role: 'assistant', content: `🎬 ${r.montage_choice!.reason}.` }])
    }
    catch (e) { toast('error', getErrorMessage(e)) } finally { setScripting(false) }
  }

  const launch = async () => {
    setCreating(true)
    try {
      const ad = await createAd(brief, board || undefined)
      setAds((prev) => [ad, ...prev]); toast('success', 'C’est parti ! Ta pub est en cours de création.')
      setBoard(null); start()
    } catch (e) { toast('error', getErrorMessage(e)) } finally { setCreating(false) }
  }

  const onFiles = async (list?: FileList | null) => {
    const files = Array.from(list || []).slice(0, multiple ? 6 : 1)
    if (!files.length) return
    setUploading(true)
    try {
      const ids: string[] = []
      for (const f of files) ids.push(await uploadLogo(f))
      await send(ids.join(','), files.length > 1 ? `📸 ${files.length} images` : `📸 ${files[0].name}`)
    }
    catch (e) { toast('error', getErrorMessage(e)) } finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  const tpl = brief.montage === 'classique' ? templates.find((t) => t.id === (brief.template as string)) : undefined
  const mont = montages.find((m) => m.id === (brief.montage as string))
  const curFmt = fmtOf(brief)
  const fmtInfo = formats.find((f) => f.id === curFmt)
  const pickable = montages.filter((m) => m.available && (!m.formats || m.formats.includes(curFmt)))

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Clapperboard className="w-6 h-6 text-primary-400" /> Studio Pub motion design
        </h1>
        <p className="text-dark-400 text-sm">Choisis ton domaine, réponds à ton motion designer IA : il creuse ton produit, écrit le script (problème → agitation → solution → appel à l’action), enregistre la voix off, monte chaque scène et ajoute les sons. Aucune vidéo à filmer.</p>
      </div>

      <div className="grid lg:grid-cols-[1fr_360px] gap-6">
        <div className="card p-0 flex flex-col h-[70vh] min-h-[520px]">
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((m, i) => <Bubble key={i} m={m} />)}
            {thinking && <div className="flex items-center gap-2 text-dark-400 text-sm"><Loader2 className="w-4 h-4 animate-spin" /> …</div>}
            {board && (
              <div className="border border-dark-700 rounded-xl p-3 bg-dark-900/60">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold text-sm flex items-center gap-2"><Wand2 className="w-4 h-4 text-primary-400" /> Script & storyboard</div>
                  <button onClick={makeScript} className="text-xs text-dark-400 hover:text-white flex items-center gap-1" disabled={scripting}>
                    <RotateCcw className="w-3 h-3" /> Autre version</button>
                </div>
                <ol className="space-y-1.5 text-sm">
                  {board.beats.map((b, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-[10px] uppercase tracking-wide shrink-0 w-28 text-primary-300 pt-0.5">{SCENE_LABELS[b.scene.type] || b.scene.type}</span>
                      <span className="text-dark-100">{b.text}</span>
                    </li>
                  ))}
                </ol>
                {board.notes?.length ? <div className="text-xs text-dark-500 mt-2">{board.notes.join(' · ')}</div> : null}
                <button onClick={launch} disabled={creating} className="btn-primary w-full mt-3 flex items-center justify-center gap-2">
                  {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Créer la vidéo
                </button>
              </div>
            )}
            <div ref={endRef} />
          </div>
          {fmtPicker && !board && formats.length > 0 && (
            <div className="px-4 pb-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
              {formats.map((f) => <FormatCard key={f.id} f={f} active={curFmt === f.id} disabled={thinking} onClick={() => send(`${f.name} — ${f.hint}`)} />)}
            </div>
          )}
          {picker && !board && montages.length > 0 && (
            <div className="px-4 pb-3 grid grid-cols-4 sm:grid-cols-8 gap-2">
              {[{ id: 'auto', name: 'Automatique', description: 'Je choisis le montage le plus adapté à ton domaine et à ton format', available: true, rhythm: 'recommandé' } as AdMontage, ...pickable].map((m) => (
                <button key={m.id} disabled={thinking} onClick={() => send(m.id === 'auto' ? '✨ Choix automatique (recommandé)' : m.name)} title={m.description}
                  className="text-left rounded-xl p-1.5 border transition-colors min-w-0 border-dark-600 hover:border-primary-500">
                  <MontageThumb id={m.id} />
                  <div className="mt-1 text-[11px] font-semibold truncate">{m.name}</div>
                  <div className="text-[10px] text-dark-400 truncate">{m.rhythm}</div>
                </button>
              ))}
            </div>
          )}
          {upload && !board && (
            <div className="px-4 pb-2">
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" multiple={multiple} className="hidden" onChange={(e) => onFiles(e.target.files)} />
              <button onClick={() => fileRef.current?.click()} disabled={uploading || thinking}
                className="btn-primary text-sm flex items-center gap-2">
                {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />} {multiple ? 'Importer des images (6 max)' : 'Importer une image'}
              </button>
            </div>
          )}
          {suggestions.length > 0 && !board && !picker && !fmtPicker && (
            <div className="px-4 pb-2 flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button key={s} onClick={() => (s === 'Créer ma pub' ? makeScript() : send(s))} disabled={thinking || scripting}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${s === 'Créer ma pub'
                    ? 'bg-primary-600 border-primary-500 text-white hover:bg-primary-500' : 'border-dark-600 text-dark-200 hover:border-primary-500 hover:text-white'}`}>
                  {scripting && s === 'Créer ma pub' ? 'Écriture du script…' : s}
                </button>
              ))}
            </div>
          )}
          {!done && (
            <form className="border-t border-dark-700 p-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(input) }}>
              <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) } }}
                placeholder="Ta réponse… (Maj+Entrée pour aller à la ligne)" className="input-field flex-1 resize-none" disabled={thinking} />
              <button type="submit" className="btn-primary px-4" disabled={thinking || !input.trim()} aria-label="Envoyer"><Send className="w-4 h-4" /></button>
            </form>
          )}
          {done && !board && (
            <div className="border-t border-dark-700 p-3 flex gap-2">
              <button onClick={start} className="btn-secondary text-sm flex items-center gap-1"><RotateCcw className="w-4 h-4" /> Recommencer</button>
            </div>
          )}
        </div>

        <div className="space-y-4">
          {fmtInfo && typeof brief.format === 'string' && (
            <div className="card p-4 flex gap-3 items-center">
              <div className="w-14 h-14 shrink-0 flex items-center justify-center"><div className={`${FORMAT_BOX[curFmt]} h-full max-w-full rounded bg-gradient-to-br from-primary-500/70 to-dark-700`} /></div>
              <div className="min-w-0"><div className="text-xs text-dark-400">Format</div>
                <div className="font-semibold">{fmtInfo.name} · {fmtInfo.size}</div>
                <div className="text-xs text-dark-400">{fmtInfo.hint}</div></div>
            </div>
          )}
          {brief.montage === 'auto' && (
            <div className="card p-4 flex gap-3 items-center">
              <div className="w-14 shrink-0"><MontageThumb id="auto" /></div>
              <div className="min-w-0"><div className="text-xs text-dark-400">Mode de montage</div>
                <div className="font-semibold">Automatique</div>
                <div className="text-xs text-dark-400">Choisi selon ton domaine, ton offre et le format, sans répéter tes dernières pubs.</div></div>
            </div>
          )}
          {mont && (
            <div className="card p-4 flex gap-3 items-center">
              <div className="w-14 shrink-0"><MontageThumb id={mont.id} /></div>
              <div className="min-w-0"><div className="text-xs text-dark-400">Mode de montage</div>
                <div className="font-semibold flex items-center gap-1"><Check className="w-4 h-4 text-primary-400" />{mont.name}</div>
                <div className="text-xs text-dark-400">{mont.description}</div></div>
            </div>
          )}
          {tpl && (
            <div className="card p-4">
              <div className="text-xs text-dark-400 mb-1">Style choisi</div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg" style={{ background: `linear-gradient(135deg, ${tpl.dark}, ${tpl.accent})` }} />
                <div><div className="font-semibold">{tpl.name}</div><div className="text-xs text-dark-400">{tpl.description}</div></div>
              </div>
            </div>
          )}
          <div>
            <h2 className="font-semibold mb-2">Mes pubs</h2>
            <div className="space-y-3">
              {ads.length === 0 && <div className="text-sm text-dark-500">Tes pubs apparaîtront ici.</div>}
              {ads.map((a) => <AdCard key={a.id} ad={a} onChange={refresh} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
