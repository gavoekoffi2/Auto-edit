interface Props {
  /** Identifiant du mode (`collage_premium`, `signature_3d`…). */
  modeId: string
  family?: string
  selected?: boolean
}

/**
 * Miniature d'un moteur de montage — ce qu'il PRODUIT, pas un emoji.
 *
 * Un emoji ne dit rien du rendu: « ✂️ » et « 🎞️ » ne permettent pas de choisir
 * entre deux moteurs. La miniature montre la mécanique réelle: pour les
 * moteurs de collage, des pièces de papier posées sur un aplat de couleur —
 * elles sont **désassemblées au repos et se posent au survol**, ce qui est
 * exactement le mouvement `collage_assemble` du rendu final. Pour les moteurs
 * viraux, un cadre vertical avec ses bandes de sous-titres qui s'allument.
 *
 * Tout est en CSS: aucune image à charger, aucune requête, et le rail de
 * moteurs reste instantané même avec dix cartes.
 */
export default function EnginePreview({ modeId, family, selected }: Props) {
  const isCollage = (family ?? '').startsWith('collage') || modeId.startsWith('collage')
  const theme = THEMES[modeId] ?? (isCollage ? THEMES.collage_premium : THEMES.signature_3d)

  return (
    <div
      aria-hidden
      className="relative h-[58px] w-[42px] shrink-0 overflow-hidden rounded-lg ring-1 ring-white/10"
      style={{ background: theme.field }}
    >
      {isCollage ? (
        <>
          {COLLAGE_PIECES.map((piece, i) => (
            <span
              key={i}
              className="absolute rounded-[2px] transition-all duration-500 ease-premium"
              style={{
                left: `${piece.x}%`,
                top: `${piece.y}%`,
                width: `${piece.size}%`,
                height: `${piece.size * 0.72}%`,
                background: theme.papers[i % theme.papers.length],
                // Au repos les pièces sont décalées et penchées; la carte
                // survolée (ou sélectionnée) les repose à leur place.
                transform: selected
                  ? 'translate(0,0) rotate(0deg)'
                  : `translate(${piece.dx}px, ${piece.dy}px) rotate(${piece.tilt}deg)`,
                transitionDelay: `${i * 70}ms`,
                boxShadow: '0 1px 2px rgba(0,0,0,0.45)',
              }}
            />
          ))}
          <span
            className="absolute inset-0 opacity-[0.18]"
            style={{
              backgroundImage: 'radial-gradient(rgba(0,0,0,0.9) 0.5px, transparent 0.6px)',
              backgroundSize: '3px 3px',
            }}
          />
        </>
      ) : (
        <>
          <span className="absolute inset-x-1.5 top-1.5 h-[26px] rounded-[3px] bg-white/12" />
          <span
            className="absolute left-1/2 top-[13px] h-3 w-3 -translate-x-1/2 rounded-full"
            style={{ background: theme.papers[0] }}
          />
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="absolute rounded-[2px] transition-all duration-500 ease-premium"
              style={{
                left: `${12 + i * 4}%`,
                top: `${62 + i * 12}%`,
                width: `${72 - i * 16}%`,
                height: '7%',
                background: i === 1 ? theme.papers[1] : 'rgba(255,255,255,0.55)',
                opacity: selected ? 1 : 0.45,
                transitionDelay: `${i * 80}ms`,
              }}
            />
          ))}
        </>
      )}
    </div>
  )
}

/** Positions en %, décalage de repos en px, inclinaison de repos en degrés. */
const COLLAGE_PIECES = [
  { x: 18, y: 14, size: 46, dx: -5, dy: -4, tilt: -12 },
  { x: 52, y: 40, size: 34, dx: 6, dy: 3, tilt: 10 },
  { x: 14, y: 58, size: 30, dx: -4, dy: 6, tilt: 8 },
]

/** Palettes reprises du verrou de style du moteur (papier coloré + crème). */
const THEMES: Record<string, { field: string; papers: string[] }> = {
  collage_premium: { field: '#E8452C', papers: ['#F7F1E3', '#1D1D1B', '#F2B705'] },
  collage_ugc_product: { field: '#2E5EAA', papers: ['#F7F1E3', '#F2B705', '#1D1D1B'] },
  collage_ugc_motion: { field: '#1B4D3E', papers: ['#F7F1E3', '#E8452C', '#EFD9A0'] },
  signature_3d: { field: '#141322', papers: ['#F2B705', '#6593ff'] },
  credit_saver_creator_edit: { field: '#101219', papers: ['#8b5cf6', '#e5e7eb'] },
}
