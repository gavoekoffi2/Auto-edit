interface Props {
  icon?: React.ReactNode
  label: string
  hint?: string
  checked: boolean
  onToggle: () => void
  disabled?: boolean
}

/**
 * Interrupteur d'option du studio.
 *
 * Un vrai `role="switch"`, pas une carte cliquable déguisée: l'état est
 * annoncé aux lecteurs d'écran et se pilote au clavier. Le rail est INTÉRIEUR
 * (creusé) et le curseur porte l'ombre — c'est ce contraste qui fait lire
 * l'état en un coup d'œil, sans dépendre de la couleur seule.
 */
export default function Toggle({ icon, label, hint, checked, onToggle, disabled }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onToggle}
      className={`group flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-all duration-300 ease-premium disabled:cursor-not-allowed disabled:opacity-40 ${
        checked
          ? 'border-primary-500/40 bg-primary-500/[0.09]'
          : 'border-white/[0.07] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]'
      }`}
    >
      {icon && (
        <span className={`shrink-0 transition-colors ${checked ? 'text-primary-300' : 'text-dark-600 group-hover:text-dark-400'}`}>
          {icon}
        </span>
      )}
      {/* Le libellé passe à la ligne plutôt que d'être tronqué: dans une
          colonne étroite, « Sous-titres animés » devenait « Sous-t… », ce qui
          oblige à deviner ce qu'on active. */}
      <span className="min-w-0 flex-1">
        <span className={`block text-[11px] font-semibold leading-snug ${checked ? 'text-white' : 'text-dark-300'}`}>
          {label}
        </span>
        {hint && <span className="mt-0.5 block text-[10px] leading-snug text-dark-600">{hint}</span>}
      </span>
      <span
        aria-hidden
        className={`relative h-[18px] w-8 shrink-0 rounded-full transition-colors duration-300 ${
          checked ? 'bg-primary-500' : 'bg-white/10'
        }`}
        style={{ boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.5)' }}
      >
        <span
          className="absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white shadow-md transition-all duration-300 ease-snap"
          style={{ left: checked ? '16px' : '2px' }}
        />
      </span>
    </button>
  )
}
