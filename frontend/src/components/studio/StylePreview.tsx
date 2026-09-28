import type { CSSProperties } from 'react'
import type { MontageId, StylePalette } from '../../api/studio'

/**
 * Aperçu animé d'un style : une mini-vidéo 9:16 dessinée en CSS qui montre la
 * GRAMMAIRE du montage (où vit le visage, comment les idées s'écrivent), pas
 * seulement ses couleurs. Boucle de 6 s, coupée si l'utilisateur réduit les
 * animations.
 */
interface Props {
  montage: MontageId
  palette: StylePalette
  headFont?: string
  playing?: boolean
  className?: string
}

const FONT: Record<string, string> = {
  Anton: '"Anton", Impact, "Arial Narrow Bold", sans-serif',
  Bebas: '"Bebas Neue", Impact, sans-serif',
  DMSerif: '"DM Serif Display", Georgia, serif',
}

function Face({ style, dim = 0 }: { style?: CSSProperties; dim?: number }) {
  return (
    <div className="sp-face" style={style}>
      <div className="sp-face-bg" />
      <div className="sp-head" />
      <div className="sp-body" />
      {dim > 0 && <div className="sp-dim" style={{ opacity: dim }} />}
    </div>
  )
}

export default function StylePreview({ montage, palette: p, headFont = 'Anton', playing = true, className = '' }: Props) {
  const vars = {
    '--a': p.accent,
    '--a2': p.accent2,
    '--d': p.dark,
    '--d2': p.dark2,
    '--l': p.light,
    '--l2': p.light2,
    '--ink': p.ink,
    '--bad': p.bad,
    '--head': FONT[headFont] ?? FONT.Anton,
  } as CSSProperties

  let scene: JSX.Element
  switch (montage) {
    case 'presentateur':
      scene = (
        <>
          <div className="sp-panel sp-anim-panel" />
          <div className="sp-panel-title sp-anim-panel">
            <b />
            <b className="short" />
          </div>
          <Face style={{ inset: 0 }} />
          <div className="sp-anim-bubble sp-bubble-face"><Face style={{ inset: 0 }} /></div>
        </>
      )
      break
    case 'fenetre':
      scene = (
        <>
          <div className="sp-back" />
          <div className="sp-headline sp-anim-type"><b /><b className="short" /></div>
          <div className="sp-window sp-anim-breathe"><Face style={{ inset: 0 }} /></div>
          <div className="sp-caption" />
        </>
      )
      break
    case 'telephone':
      scene = (
        <>
          <div className="sp-back" />
          <div className="sp-phone"><Face style={{ inset: 0 }} /><i className="sp-notch" /></div>
          <div className="sp-chat sp-anim-pop1" />
          <div className="sp-chat me sp-anim-pop2" />
        </>
      )
      break
    case 'kinetique':
      scene = (
        <>
          <Face style={{ inset: 0 }} dim={0.55} />
          <div className="sp-kin">
            <span className="sp-anim-slam1">TON</span>
            <span className="sp-anim-slam2 hot">IDÉE</span>
            <span className="sp-anim-slam3">CLAQUE</span>
          </div>
        </>
      )
      break
    case 'ecran_scinde':
      scene = (
        <>
          <Face style={{ left: 0, top: 0, right: 0, height: '60%' }} />
          <div className="sp-band"><div className="sp-band-rule" /><b className="sp-anim-type" /><b className="short sp-anim-type2" /><i /></div>
        </>
      )
      break
    case 'zoom_rythme':
      scene = (
        <>
          <div className="sp-zoom"><Face style={{ inset: 0 }} /></div>
          <div className="sp-bigword sp-anim-slam2">WOW</div>
          <div className="sp-caption mid" />
        </>
      )
      break
    case 'mur_polaroid':
      scene = (
        <>
          <div className="sp-back paper" />
          <div className="sp-polaroid"><Face style={{ left: 6, top: 6, right: 6, bottom: 22 }} /></div>
          <div className="sp-note sp-anim-pop1" />
          <div className="sp-note two sp-anim-pop2" />
        </>
      )
      break
    case 'journal_tv':
      scene = (
        <>
          <Face style={{ inset: 0 }} />
          <div className="sp-l3 sp-anim-slide"><i /><b /></div>
          <div className="sp-ticker"><span>• TITRE • IDÉE • APPEL • TITRE • IDÉE • APPEL</span></div>
        </>
      )
      break
    case 'magazine':
      scene = (
        <>
          <Face style={{ inset: 0 }} />
          <div className="sp-mast">MARQUE</div>
          <div className="sp-cover sp-anim-type"><b /><b className="short" /><i /></div>
        </>
      )
      break
    case 'stories':
      scene = (
        <>
          <Face style={{ inset: 0 }} />
          <div className="sp-igbars"><i /><i /><i className="on" /></div>
          <div className="sp-igsticker sp-anim-pop1"><b /><i /></div>
          <div className="sp-igfield" />
        </>
      )
      break
    case 'jeu_video':
      scene = (
        <>
          <Face style={{ inset: 0 }} />
          <div className="sp-hud"><i /><i className="xp" /></div>
          <div className="sp-dialog sp-anim-slide"><b /><b className="short" /></div>
        </>
      )
      break
    case 'podcast':
      scene = (
        <>
          <div className="sp-back" />
          <div className="sp-wave sp-anim-breathe" />
          <Face style={{ left: '22%', top: '14%', width: '56%', aspectRatio: '1', borderRadius: '50%' }} />
          <div className="sp-player"><i /><b /></div>
        </>
      )
      break
    case 'documentaire':
      scene = (
        <>
          <Face style={{ inset: 0, filter: 'saturate(.6) sepia(.15)' }} />
          <div className="sp-letter top" /><div className="sp-letter bot" />
          <div className="sp-chapter sp-anim-type"><i /><b /></div>
        </>
      )
      break
    case 'bento':
      scene = (
        <>
          <div className="sp-back" />
          <Face style={{ left: '4%', top: '3%', width: '92%', height: '56%', borderRadius: '10px' }} />
          <div className="sp-tile a sp-anim-pop1" /><div className="sp-tile b sp-anim-pop2" /><div className="sp-tile c" />
        </>
      )
      break
    case 'voyage':
      scene = (
        <>
          <div className="sp-map sp-anim-travel">
            <div className="sp-route" />
            <div className="sp-page p1"><Face style={{ inset: '4%', borderRadius: '6px' }} /></div>
            <div className="sp-page p2"><b /><b className="short" /></div>
            <div className="sp-page p3"><i /></div>
          </div>
        </>
      )
      break
    default:
      scene = (
        <>
          <Face style={{ inset: 0 }} />
          <div className="sp-card sp-anim-card"><i /><b /><b className="short" /></div>
          <div className="sp-caption" />
        </>
      )
  }

  return (
    <div className={`sp-root ${playing ? 'is-playing' : ''} ${className}`} style={vars} aria-hidden>
      {scene}
    </div>
  )
}
