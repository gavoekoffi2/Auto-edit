import { useEffect, useRef, useState } from 'react'
import { Play } from 'lucide-react'
import { getStreamUrl } from '../../api/videos'

interface Props {
  videoId: string
  /** Dégradé de repli, aussi visible pendant le chargement de l'image. */
  gradient: string
  duration?: number | null
  badge?: string
}

/**
 * Vignette d'une vidéo — une VRAIE image extraite du fichier.
 *
 * La bibliothèque affichait un dégradé de couleur et une icône de pellicule:
 * toutes les vidéos se ressemblaient, et retrouver la bonne demandait de lire
 * les titres un par un. Une image vaut la lecture de dix titres.
 *
 * Trois précautions, parce qu'une vignette ne doit jamais coûter cher:
 *
 *   * elle ne charge qu'à l'APPROCHE du viewport (IntersectionObserver), donc
 *     une bibliothèque de cinquante vidéos ne déclenche pas cinquante requêtes;
 *   * `preload="metadata"` + `#t=` : le navigateur ne récupère que l'en-tête
 *     et la frame demandée, pas la vidéo;
 *   * en cas d'échec (format exotique, réseau coupé, codec non supporté), on
 *     retombe silencieusement sur le dégradé. Une vignette manquante n'est pas
 *     une erreur à signaler à l'utilisateur.
 */
export default function VideoThumb({ videoId, gradient, duration, badge }: Props) {
  const holder = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const node = holder.current
    if (!node || visible) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '220px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [visible])

  return (
    <div
      ref={holder}
      className={`relative h-[72px] w-full shrink-0 overflow-hidden rounded-xl bg-gradient-to-br sm:w-[124px] ${gradient}`}
    >
      {visible && !failed && (
        <video
          // La frame d'une seconde: la toute première est souvent noire (fondu
          // d'ouverture de caméra), ce qui donnerait une vignette vide.
          src={`${getStreamUrl(videoId)}#t=1`}
          preload="metadata"
          muted
          playsInline
          tabIndex={-1}
          aria-hidden
          onLoadedData={() => setReady(true)}
          onError={() => setFailed(true)}
          className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-500 ease-premium ${
            ready ? 'opacity-100' : 'opacity-0'
          }`}
        />
      )}

      {/* Voile sombre: garantit le contraste de la pastille de durée et du
          bouton de lecture quelle que soit la frame extraite. */}
      <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-black/15" aria-hidden />

      <span className="absolute inset-0 grid place-items-center">
        <span className="grid h-9 w-9 place-items-center rounded-full border border-white/20 bg-black/35 backdrop-blur-sm transition-transform duration-500 ease-premium group-hover:scale-110">
          <Play className="ml-0.5 h-3.5 w-3.5 fill-white/85 text-white/85" />
        </span>
      </span>

      {duration != null && (
        <span className="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums">
          {formatDuration(duration)}
        </span>
      )}
      {badge && (
        <span className="absolute left-1.5 top-1.5 rounded bg-emerald-500/90 px-1.5 py-0.5 text-[9px] font-bold tracking-wider">
          {badge}
        </span>
      )}
    </div>
  )
}

function formatDuration(sec: number) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
