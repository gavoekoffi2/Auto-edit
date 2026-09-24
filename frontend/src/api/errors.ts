import axios from 'axios'

/**
 * Retire le préfixe de code stable ajouté par le backend (« [RENDER_FAILED] … »)
 * pour n'afficher que le message destiné à l'utilisateur.
 */
export function stripErrorCode(message: string): string {
  return message.replace(/^\[[A-Z0-9_]+\]\s*/, '').trim()
}

function fromDetail(detail: unknown): string | null {
  if (!detail) return null
  if (typeof detail === 'string') return stripErrorCode(detail)
  // Erreurs produit: { code, message, request_id }
  if (typeof detail === 'object' && !Array.isArray(detail) && 'message' in detail) {
    const msg = (detail as { message?: unknown }).message
    return typeof msg === 'string' ? stripErrorCode(msg) : null
  }
  // Erreurs de validation FastAPI: [{ msg, loc, ... }]
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
      .map((m) => m.replace(/^Value error,\s*/i, ''))
      .filter(Boolean)
    return msgs.length ? msgs.join('. ') : null
  }
  return null
}

/**
 * Message lisible (en français) pour n'importe quelle erreur d'appel API.
 * Ne renvoie JAMAIS un objet: un objet passé à un toast ou à du JSX fait
 * planter l'affichage React.
 */
export function getApiErrorMessage(err: unknown, fallback = 'Une erreur est survenue. Réessaie.'): string {
  if (axios.isAxiosError(err)) {
    const fromApi = fromDetail(err.response?.data?.detail)
    if (fromApi) return fromApi
    const status = err.response?.status
    if (!err.response) return 'Connexion impossible au serveur. Vérifie ta connexion internet puis réessaie.'
    if (status === 413) return 'Fichier trop lourd pour le serveur.'
    if (status === 429) return 'Trop de tentatives. Patiente un instant puis réessaie.'
    if (status && status >= 500) return 'Le serveur rencontre un problème momentané. Réessaie dans quelques minutes.'
    return fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}
