"""Mise en file des jobs Celery APRÈS le commit de la transaction.

Bug corrigé: les routes appelaient ``apply_async`` avant que la session
FastAPI ne commite (le commit a lieu à la fin de la requête, dans
``get_db``). Un worker rapide dépilait la tâche, ne trouvait pas encore la
ligne Job (« Job not found ») et abandonnait: le job restait « pending » pour
toujours et bloquait en plus le quota de jobs simultanés de l'utilisateur.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job

logger = logging.getLogger(__name__)


async def commit_and_dispatch(db: AsyncSession, job: Job, task) -> None:
    """Commite *job* puis l'envoie au worker (task_id = id du job).

    Si le broker est injoignable, le job est marqué ``failed`` (il ne doit pas
    rester « pending » et consommer le quota) et l'API répond 503.
    """
    await db.commit()
    job_id = str(job.id)
    try:
        # task_id = id du job: c'est ce qui rend `POST /jobs/{id}/cancel`
        # opérant (revoke cible cet identifiant).
        task.apply_async(args=[job_id], task_id=job_id)
    except Exception as exc:  # noqa: BLE001 - broker down, config, réseau
        logger.error("Could not enqueue job %s: %s", job_id, exc)
        job.status = "failed"
        job.error_message = (
            "[QUEUE_UNAVAILABLE] Le service de traitement est momentanément "
            "indisponible. Réessaie dans quelques minutes."
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de traitement est momentanément indisponible. Réessaie dans quelques minutes.",
        ) from exc
