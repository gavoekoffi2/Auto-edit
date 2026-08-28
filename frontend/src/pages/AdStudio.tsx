import { useMemo, useState } from 'react'
import { ArrowRight, Check, Clapperboard, Loader2, MessageSquareText, Play, Sparkles } from 'lucide-react'
import { createVoiceover, previewBrief, type AdTemplateId, type BriefPreview } from '../api/briefs'
import { toast } from '../components/ui/Toast'
import Reveal from '../components/ui/Reveal'

const templates: Array<{ id: AdTemplateId; label: string; family: 'Publicité' | 'Face caméra'; description: string; accent: string }> = [
  { id: 'direct_response', label: 'Direct Response', family: 'Publicité', description: 'Hook, problème, bénéfices, preuves et CTA avec produit ancré.', accent: 'from-cyan-400 to-blue-600' },
  { id: 'urgency_proof', label: 'Urgence & Preuve', family: 'Publicité', description: 'Compte à rebours, contraste problème/solution et preuve sociale.', accent: 'from-rose-400 to-red-600' },
  { id: 'saas_explainer', label: 'Démonstration SaaS', family: 'Publicité', description: 'Écrans, fonctionnalités et parcours produit étape par étape.', accent: 'from-violet-400 to-indigo-600' },
  { id: 'facecam_editorial', label: 'Face caméra éditorial', family: 'Face caméra', description: 'Captions en pilule, coupes propres et B-roll contextuel.', accent: 'from-amber-300 to-orange-600' },
  { id: 'facecam_neon', label: 'Face caméra néon', family: 'Face caméra', description: 'Jump cuts rapides, mots forts et accents lumineux.', accent: 'from-fuchsia-400 to-cyan-500' },
  { id: 'facecam_notes', label: 'Face caméra notes', family: 'Face caméra', description: 'Annotations, flèches et surlignages façon carnet.', accent: 'from-emerald-300 to-teal-700' },
]

const examples = [
  'Je vends une formation qui aide les e-commerçants à répondre plus vite et à conclure davantage de ventes.',
  'Notre plateforme permet aux petites entreprises de centraliser leurs factures et de gagner du temps chaque semaine.',
]

function formatTime(value: number) {
  return `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2, '0')}`
}

export default function AdStudio() {
  const [templateId, setTemplateId] = useState<AdTemplateId>('direct_response')
  const [description, setDescription] = useState('')
  const [brandName, setBrandName] = useState('')
  const [audience, setAudience] = useState('')
  const [offer, setOffer] = useState('')
  const [proof, setProof] = useState('')
  const [cta, setCta] = useState('Découvre l’offre')
  const [tone, setTone] = useState<'expert' | 'direct' | 'premium' | 'chaleureux'>('direct')
  const [format, setFormat] = useState<'9:16' | '1:1' | '16:9'>('9:16')
  const [duration, setDuration] = useState(45)
  const [preview, setPreview] = useState<BriefPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [voiceoverLoading, setVoiceoverLoading] = useState(false)

  const selected = useMemo(() => templates.find((item) => item.id === templateId) ?? templates[0], [templateId])

  const handleGenerate = async () => {
    if (description.trim().length < 20) {
      toast('error', 'Décris ton entreprise en au moins une phrase complète.')
      return
    }
    setLoading(true)
    try {
      const result = await previewBrief({
        description, template_id: templateId, brand_name: brandName, audience, offer, proof, cta, tone, format, duration_s: duration,
      })
      setPreview(result)
      toast('success', 'Storyboard publicitaire généré')
    } catch {
      toast('error', 'Impossible de générer le storyboard pour le moment')
    } finally {
      setLoading(false)
    }
  }

  const handleVoiceover = async () => {
    if (!preview) return
    setVoiceoverLoading(true)
    try {
      const script = preview.scenes.map((scene) => scene.narration).join(' ')
      const blob = await createVoiceover(script)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'voiceover-publicite.mp3'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
      toast('success', 'Voix off générée et téléchargée')
    } catch {
      toast('error', 'Configure un fournisseur TTS pour générer la voix off')
    } finally {
      setVoiceoverLoading(false)
    }
  }

  return (
    <div className="relative isolate overflow-x-clip">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] overflow-hidden" aria-hidden>
        <div className="cf-aurora left-[-8%] top-[-30%] h-[380px] w-[380px] bg-primary-600/40" />
        <div className="cf-aurora right-[-6%] top-[-20%] h-[320px] w-[320px] bg-fuchsia-600/25" style={{ animationDelay: '-7s' }} />
        <div className="cf-grid-dots absolute inset-0 opacity-70" />
      </div>
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <Reveal>
          <div className="max-w-3xl">
            <p className="flex items-center gap-2 text-sm font-semibold text-primary-300"><Sparkles className="h-4 w-4" /> Ad Studio</p>
            <h1 className="mt-3 text-3xl font-bold sm:text-5xl">Transforme ton brief en <span className="gradient-text">vidéo publicitaire</span></h1>
            <p className="mt-4 max-w-2xl text-dark-400">Décris ton entreprise, ton audience et ton offre. Le moteur construit une narration, un découpage scène par scène et un plan de rendu adapté à ton template.</p>
          </div>
        </Reveal>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.05fr_.95fr]">
          <Reveal>
            <section className="cf-card card !p-6">
              <div className="mb-5 flex items-center gap-2"><MessageSquareText className="h-5 w-5 text-primary-300" /><h2 className="text-lg font-semibold">Ton brief</h2></div>
              <label className="text-xs font-semibold uppercase tracking-wider text-dark-400">Description de l’entreprise et de l’offre</label>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={6} placeholder="Exemple : Nous aidons les boutiques en ligne à…" className="input mt-2 min-h-[150px] resize-y" />
              <div className="mt-2 flex flex-wrap gap-2">{examples.map((example) => <button key={example} type="button" onClick={() => setDescription(example)} className="rounded-full border border-white/10 px-3 py-1.5 text-[11px] text-dark-300 transition hover:border-primary-400/40 hover:text-white">Utiliser un exemple</button>)}</div>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-xs text-dark-400">Nom de marque<input value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder="Kora Studio" className="input mt-2" /></label>
                <label className="text-xs text-dark-400">Audience cible<input value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="E-commerçants africains" className="input mt-2" /></label>
                <label className="text-xs text-dark-400">Offre à mettre en avant<input value={offer} onChange={(e) => setOffer(e.target.value)} placeholder="Assistant de vente WhatsApp" className="input mt-2" /></label>
                <label className="text-xs text-dark-400">Preuve ou résultat<input value={proof} onChange={(e) => setProof(e.target.value)} placeholder="120 clients accompagnés" className="input mt-2" /></label>
                <label className="text-xs text-dark-400">Appel à l’action<input value={cta} onChange={(e) => setCta(e.target.value)} placeholder="Teste maintenant" className="input mt-2" /></label>
                <label className="text-xs text-dark-400">Ton<select value={tone} onChange={(e) => setTone(e.target.value as typeof tone)} className="input mt-2"><option value="direct">Direct et vendeur</option><option value="expert">Expert et pédagogique</option><option value="premium">Premium et posé</option><option value="chaleureux">Chaleureux et humain</option></select></label>
              </div>
              <div className="mt-6 flex flex-wrap items-end gap-4">
                <label className="text-xs text-dark-400">Format<select value={format} onChange={(e) => setFormat(e.target.value as typeof format)} className="input mt-2"><option>9:16</option><option>1:1</option><option>16:9</option></select></label>
                <label className="text-xs text-dark-400">Durée<select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="input mt-2"><option value={30}>30 secondes</option><option value={45}>45 secondes</option><option value={60}>60 secondes</option></select></label>
                <button type="button" onClick={handleGenerate} disabled={loading} className="btn-primary ml-auto flex items-center gap-2">{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Générer le storyboard</button>
              </div>
            </section>
          </Reveal>

          <Reveal delay={100}>
            <section className="cf-card card !p-6">
              <div className="mb-5 flex items-center gap-2"><Clapperboard className="h-5 w-5 text-primary-300" /><h2 className="text-lg font-semibold">Choisis un template</h2></div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                {templates.map((template) => (
                  <button key={template.id} type="button" onClick={() => setTemplateId(template.id)} className={`group flex items-start gap-3 rounded-2xl border p-3 text-left transition ${template.id === templateId ? 'border-primary-400/70 bg-primary-500/10' : 'border-white/10 bg-white/[.03] hover:border-white/20'}`}>
                    <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${template.accent} text-white shadow-lg`}><Play className="h-4 w-4 fill-current" /></span>
                    <span className="min-w-0"><span className="flex items-center gap-2 text-sm font-semibold">{template.label}{template.id === templateId && <Check className="h-3.5 w-3.5 text-primary-300" />}</span><span className="mt-1 block text-xs leading-relaxed text-dark-400">{template.description}</span><span className="mt-2 inline-flex rounded-full bg-white/5 px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-dark-500">{template.family}</span></span>
                  </button>
                ))}
              </div>
              <div className="mt-5 rounded-2xl border border-white/10 bg-white/[.03] p-4"><p className="text-xs font-semibold uppercase tracking-wider text-dark-500">Rendu sélectionné</p><p className="mt-2 text-xl font-semibold">{selected.label}</p><p className="mt-1 text-sm text-dark-400">{selected.description}</p></div>
            </section>
          </Reveal>
        </div>

        {preview && <Reveal>
          <section className="mt-6 cf-card card !p-6">
            <div className="flex flex-col gap-3 border-b border-white/10 pb-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-primary-300">Storyboard prêt</p><h2 className="mt-1 text-2xl font-bold">{preview.title}</h2><p className="mt-1 text-sm text-dark-400">{preview.summary}</p></div><span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-bold text-emerald-300">{preview.format} · {preview.duration_s}s</span></div>
            {preview.warnings.length > 0 && <p className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/10 p-3 text-xs text-amber-200">{preview.warnings.join(' ')}</p>}
            <div className="mt-5 grid gap-3 md:grid-cols-2 lg:grid-cols-3">{preview.scenes.map((scene) => <article key={scene.order} className="rounded-2xl border border-white/10 bg-dark-950/50 p-4"><div className="flex items-center justify-between"><span className="rounded-full bg-primary-500/15 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-primary-200">{scene.order}. {scene.role}</span><span className="text-[11px] text-dark-500">{formatTime(scene.start_s)}–{formatTime(scene.end_s)}</span></div><p className="mt-3 text-sm font-medium text-white">{scene.text_overlay}</p><p className="mt-2 text-xs leading-relaxed text-dark-400">{scene.narration}</p><p className="mt-3 border-t border-white/10 pt-3 text-[11px] text-dark-500">{scene.motion}</p></article>)}</div>
            <div className="mt-5 flex flex-wrap items-center gap-3"><button type="button" onClick={handleVoiceover} disabled={voiceoverLoading} className="btn-accent flex items-center gap-2">{voiceoverLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquareText className="h-4 w-4" />} Générer la voix off</button><button type="button" className="btn-primary flex items-center gap-2"><ArrowRight className="h-4 w-4" /> Préparer le rendu</button><span className="text-xs text-dark-500">La voix off nécessite `ELEVENLABS_API_KEY`. Le rendu utilisera les assets de marque et médias fournis.</span></div>
          </section>
        </Reveal>}
      </div>
    </div>
  )
}
