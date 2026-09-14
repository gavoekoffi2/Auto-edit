import { PenTool } from 'lucide-react'
import type {
  IllustrationAiMode,
  IllustrationIntensity,
  IllustrationStyle,
  JobOptions,
} from '../../api/jobs'

const STYLES: { value: IllustrationStyle; label: string; hint: string }[] = [
  { value: 'professional', label: 'Professional', hint: 'Cartes nettes, bleu profond' },
  { value: 'education', label: 'Education', hint: 'Papier chaud, tracé au feutre' },
  { value: 'business', label: 'Business', hint: 'Sobre, teal et or' },
  { value: 'technology', label: 'Tech', hint: 'Cyan, diagrammes denses' },
  { value: 'whiteboard', label: 'Whiteboard', hint: 'Dessiné à la main, encre sur blanc' },
  { value: 'minimal', label: 'Minimal', hint: 'Noir et blanc, typographie seule' },
]

const INTENSITIES: { value: IllustrationIntensity; label: string; hint: string }[] = [
  { value: 'low', label: 'Basse', hint: 'Rare, uniquement l’évident' },
  { value: 'medium', label: 'Moyenne', hint: 'Équilibré (défaut)' },
  { value: 'high', label: 'Haute', hint: 'Dès qu’un passage s’y prête' },
]

const AI_MODES: { value: IllustrationAiMode; label: string; hint: string }[] = [
  { value: 'offline', label: 'Offline', hint: 'Aucun réseau, aucune clé' },
  { value: 'free', label: 'Free AI', hint: 'Nécessite un endpoint configuré' },
  { value: 'cloud', label: 'Cloud AI', hint: 'Nécessite une clé configurée' },
]

interface Props {
  options: JobOptions
  onChange: (patch: Partial<JobOptions>) => void
}

/**
 * Réglages du moteur d'illustration automatique.
 *
 * Les trois axes correspondent exactement aux leviers du moteur : la direction
 * artistique, la densité d'illustrations sur la timeline, et la source
 * d'intelligence sémantique.
 */
export default function IllustrationPanel({ options, onChange }: Props) {
  const style = options.illustration_style || 'professional'
  const intensity = options.illustration_intensity || 'medium'
  const aiMode = options.illustration_ai_mode || 'offline'

  return (
    <div className="mt-4 rounded-xl border border-dark-700 bg-dark-800/40 p-3">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <PenTool className="h-4 w-4 text-primary-400" />
        Illustrations automatiques
      </div>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-dark-400" htmlFor="ill-style">
            Style
          </label>
          <select
            id="ill-style"
            value={style}
            onChange={(e) =>
              onChange({ illustration_style: e.target.value as IllustrationStyle })
            }
            className="w-full rounded-lg border border-dark-700 bg-dark-800 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
          >
            {STYLES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label} — {s.hint}
              </option>
            ))}
          </select>
        </div>

        <div>
          <span className="mb-1 block text-xs text-dark-400">Intensité</span>
          <div className="grid grid-cols-3 gap-2">
            {INTENSITIES.map((i) => (
              <button
                key={i.value}
                type="button"
                title={i.hint}
                onClick={() => onChange({ illustration_intensity: i.value })}
                className={`rounded-lg border px-2 py-2 text-xs transition ${
                  intensity === i.value
                    ? 'border-primary-500 bg-primary-500/10 text-primary-300'
                    : 'border-dark-700 bg-dark-800 text-dark-400 hover:border-dark-600'
                }`}
              >
                {i.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <span className="mb-1 block text-xs text-dark-400">Mode</span>
          <div className="grid grid-cols-3 gap-2">
            {AI_MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                title={m.hint}
                onClick={() => onChange({ illustration_ai_mode: m.value })}
                className={`rounded-lg border px-2 py-2 text-xs transition ${
                  aiMode === m.value
                    ? 'border-primary-500 bg-primary-500/10 text-primary-300'
                    : 'border-dark-700 bg-dark-800 text-dark-400 hover:border-dark-600'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          {aiMode === 'offline' ? (
            <p className="mt-2 text-xs text-emerald-300/80">
              Aucun appel réseau, aucune clé API : l’analyse du discours et le
              dessin sont entièrement locaux.
            </p>
          ) : (
            <p className="mt-2 text-xs text-amber-300/80">
              Si le fournisseur n’est pas configuré ou ne répond pas, le moteur
              retombe automatiquement sur l’analyse locale.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
