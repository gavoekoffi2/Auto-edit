"""Taxonomie d'erreurs produit — codes stables + messages utilisateur FR.

Chaque erreur exposée à l'utilisateur porte:
  * un CODE stable (contrat frontend/support, ne change jamais) ;
  * un message utilisateur en français, sans détail interne ;
  * le statut HTTP approprié.

Le détail technique part dans les logs avec le request-id / job-id, jamais
dans la réponse. Côté worker, préfixer ``error_message`` par ``[CODE]``
suffit pour que le frontend et le support retrouvent la cause.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class ProductError:
    code: str
    http_status: int
    user_message: str


ERRORS: dict[str, ProductError] = {e.code: e for e in [
    # --- import / URL ------------------------------------------------------
    ProductError("URL_INVALID", 400, "URL invalide. Vérifie le lien et réessaie."),
    ProductError("URL_FORBIDDEN_HOST", 400, "Cette URL pointe vers un réseau interdit."),
    ProductError("URL_UNSUPPORTED", 400,
                 "Impossible de lire cette URL. Vérifie que la vidéo est publique."),
    ProductError("SOURCE_PRIVATE", 400,
                 "Cette vidéo est privée ou inaccessible. Utilise une vidéo publique."),
    ProductError("SOURCE_LIVE", 400,
                 "Les directs ne sont pas pris en charge. Attends la fin du live."),
    ProductError("SOURCE_TOO_LONG", 400,
                 "Vidéo trop longue pour ton plan. Passe à un plan supérieur ou choisis une vidéo plus courte."),
    ProductError("SOURCE_TOO_LARGE", 400, "Fichier source trop volumineux."),
    ProductError("DOWNLOAD_FAILED", 502,
                 "Le téléchargement de la vidéo a échoué. Réessaie dans quelques minutes."),
    # --- quotas --------------------------------------------------------------
    ProductError("QUOTA_MONTHLY_REACHED", 429,
                 "Quota mensuel atteint pour ton plan. Passe en Pro pour continuer."),
    ProductError("QUOTA_CONCURRENT_JOBS", 429,
                 "Trop de traitements en cours. Attends la fin d'un traitement ou passe à un plan supérieur."),
    ProductError("QUOTA_CLIPS_PER_JOB", 400,
                 "Nombre de clips demandé au-dessus de la limite de ton plan."),
    # --- traitement -----------------------------------------------------------
    ProductError("NO_SPEECH", 422,
                 "Aucune parole exploitable détectée dans cette vidéo."),
    ProductError("TRANSCRIPTION_FAILED", 500,
                 "La transcription a échoué. Réessaie ; si le problème persiste contacte le support."),
    ProductError("AI_UNAVAILABLE", 503,
                 "L'analyse IA est momentanément indisponible. Réessaie plus tard."),
    ProductError("RENDER_FAILED", 500,
                 "Le rendu vidéo a échoué. Réessaie ; si le problème persiste contacte le support."),
    ProductError("DISK_FULL", 507,
                 "Espace disque serveur insuffisant. Réessaie dans quelques minutes."),
    # --- ressources -----------------------------------------------------------
    ProductError("JOB_NOT_FOUND", 404, "Traitement introuvable."),
    ProductError("JOB_NOT_READY", 400, "Le traitement n'est pas encore terminé."),
    ProductError("CLIP_NOT_FOUND", 404, "Clip introuvable."),
    ProductError("FILE_EXPIRED", 410,
                 "Ce fichier a expiré et a été supprimé du serveur. Relance le traitement."),
    ProductError("VIDEO_NOT_FOUND", 404, "Vidéo introuvable."),
]}


def http_error(code: str, request_id: str | None = None) -> HTTPException:
    """HTTPException prête à lever pour *code* (contrat: {code, message, request_id})."""
    err = ERRORS.get(code) or ProductError(code, 500, "Erreur interne. Contacte le support.")
    detail: dict = {"code": err.code, "message": err.user_message}
    if request_id:
        detail["request_id"] = request_id
    return HTTPException(status_code=err.http_status, detail=detail)


def tag(code: str, technical: str = "") -> str:
    """Message d'erreur worker, préfixé par le code stable: ``[CODE] détail``."""
    err = ERRORS.get(code)
    base = f"[{code}] {err.user_message if err else ''}".strip()
    if technical:
        base += f" ({technical[:300]})"
    return base
