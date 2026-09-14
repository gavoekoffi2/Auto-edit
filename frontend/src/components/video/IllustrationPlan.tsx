import type { IllustrationPlanEntry } from '../../api/jobs'

const TYPE_LABELS: Record<string, string> = {
  whiteboard: 'Whiteboard',
  motion_graphics: 'Motion graphics',
  diagram: 'Diagramme',
  flowchart: 'Flowchart',
  process: 'Processus',
  timeline: 'Timeline',
  comparison: 'Comparaison',
  statistics: 'Statistiques',
  infographic: 'Infographie',
  concept: 'Concept',
  ui_explainer: 'Interface',
  kinetic_typography: 'Typographie',
}

interface Props {
  plan: IllustrationPlanEntry[]
  coverage?: number
}

/**
 * Ce que le moteur a décidé d'illustrer, et quand.
 *
 * C'est la preuve, pour l'utilisateur, que les animations ne sont pas posées
 * au hasard : chaque ligne porte son horodatage, son type et son score.
 */
export default function IllustrationPlan({ plan, coverage }: Props) {
  if (!plan?.length) return null

  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-semibold">Plan d’illustration</h3>
        {typeof coverage === 'number' && (
          <span className="text-xs text-dark-500">
            {(coverage * 100).toFixed(0)} % de la vidéo illustrée
          </span>
        )}
      </div>
      <ul className="space-y-2">
        {plan.map((entry) => (
          <li
            key={entry.scene_id}
            className="flex items-start gap-3 rounded-lg border border-dark-700 bg-dark-800/40 px-3 py-2"
          >
            <span className="mt-0.5 font-mono text-xs text-primary-400">{entry.at}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                {TYPE_LABELS[entry.visual_type] || entry.visual_type}
              </div>
              <div className="truncate text-xs text-dark-400" title={entry.concept}>
                « {entry.concept} »
              </div>
            </div>
            <span className="whitespace-nowrap text-xs text-dark-500">
              {entry.duration.toFixed(1)} s
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
