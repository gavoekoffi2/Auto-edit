/**
 * Marque CutForge — un carré forgé traversé par la lame de coupe,
 * avec le triangle "play" qui en ressort. Lisible de 16 px à 96 px.
 */
export default function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="cf-bg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3f72ff" />
          <stop offset="0.55" stopColor="#7c3aed" />
          <stop offset="1" stopColor="#f97316" />
        </linearGradient>
        <linearGradient id="cf-blade" x1="10" y1="40" x2="40" y2="8" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="1" stopColor="#bdf6ff" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="12" fill="url(#cf-bg)" />
      <rect x="2" y="2" width="44" height="44" rx="12" fill="black" fillOpacity="0.18" />
      {/* triangle play forgé */}
      <path d="M19 14.5 L34 24 L19 33.5 Z" fill="white" />
      {/* la lame de coupe traverse en diagonale */}
      <path d="M10.5 38.5 L37 11" stroke="url(#cf-blade)" strokeWidth="3.4" strokeLinecap="round" />
      {/* étincelle de forge */}
      <path d="M37.5 9 l1.1 2.4 2.4 1.1 -2.4 1.1 -1.1 2.4 -1.1 -2.4 -2.4 -1.1 2.4 -1.1 Z" fill="#ffd76a" />
    </svg>
  )
}
