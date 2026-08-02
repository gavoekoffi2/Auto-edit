import { forwardRef, type HTMLAttributes } from 'react'

type Tone = 'raised' | 'quiet' | 'glass'

interface Props extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone
  /** Le halo suit le curseur. Réservé aux surfaces cliquables. */
  interactive?: boolean
  /** Retire le padding interne (média plein cadre, tableaux). */
  flush?: boolean
}

const tones: Record<Tone, string> = {
  raised: 'panel-flush',
  quiet: 'panel-quiet',
  glass: 'glass-panel rounded-2xl',
}

/**
 * La brique de surface de toute l'application connectée.
 *
 * Une seule façon de poser un bloc de contenu: même rayon, même filet, même
 * élévation. Les écrans qui composaient leurs propres `bg-white/[0.03]
 * border-white/10` divergeaient au fil des ajouts — ici, une carte ne peut
 * pas être « presque » comme les autres.
 */
const Surface = forwardRef<HTMLDivElement, Props>(function Surface(
  { tone = 'raised', interactive = false, flush = false, className = '', children, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={`${tones[tone]} ${interactive ? 'cf-card' : ''} ${flush ? '' : 'p-5 sm:p-6'} ${className}`}
      onMouseMove={
        interactive
          ? (event) => {
              const box = event.currentTarget.getBoundingClientRect()
              event.currentTarget.style.setProperty('--gx', `${event.clientX - box.left}px`)
              event.currentTarget.style.setProperty('--gy', `${event.clientY - box.top}px`)
              rest.onMouseMove?.(event)
            }
          : rest.onMouseMove
      }
      {...rest}
    >
      {children}
    </div>
  )
})

export default Surface
