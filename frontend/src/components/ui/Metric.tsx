import { useEffect, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import Surface from './Surface'

interface Props {
  icon: LucideIcon
  label: string
  value: number
  /** Teinte de l'icône: la seule couleur de la tuile, tout le reste est neutre. */
  tint?: 'primary' | 'emerald' | 'amber' | 'iris'
  suffix?: string
  hint?: string
}

const tints = {
  primary: 'text-primary-300 bg-primary-500/12 ring-primary-500/20',
  emerald: 'text-emerald-300 bg-emerald-400/10 ring-emerald-400/20',
  amber: 'text-amber-300 bg-amber-400/10 ring-amber-400/20',
  iris: 'text-iris-300 bg-iris-500/12 ring-iris-500/20',
}

/**
 * Compteur qui monte jusqu'à sa valeur au premier affichage.
 *
 * Le chiffre n'est pas décoratif: le voir se poser attire l'œil là où il faut
 * une fois, puis se tait. On n'anime QUE la première apparition — un chiffre
 * qui rejoue son animation à chaque rafraîchissement devient du bruit.
 */
function useCountUp(target: number, duration = 900) {
  const [display, setDisplay] = useState(target)
  const animated = useRef(false)

  useEffect(() => {
    if (animated.current) {
      setDisplay(target)
      return
    }
    animated.current = true
    if (target <= 0 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(target)
      return
    }
    let frame = 0
    const started = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / duration)
      // easeOutExpo: l'essentiel du chemin est fait tout de suite, la fin se
      // pose — c'est la même courbe que le reste de l'interface.
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
      setDisplay(Math.round(target * eased))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])

  return display
}

export default function Metric({ icon: Icon, label, value, tint = 'primary', suffix, hint }: Props) {
  const display = useCountUp(value)
  return (
    <Surface className="flex items-center gap-4">
      <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ring-1 ${tints[tint]}`}>
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <p className="font-display text-2xl font-bold leading-none tabular-nums">
          {display}
          {suffix && <span className="ml-0.5 text-base font-semibold text-dark-500">{suffix}</span>}
        </p>
        <p className="mt-1.5 truncate text-xs text-dark-400">{label}</p>
        {hint && <p className="mt-0.5 truncate text-[11px] text-dark-600">{hint}</p>}
      </div>
    </Surface>
  )
}
