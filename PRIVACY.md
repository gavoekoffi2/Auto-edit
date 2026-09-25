# Confidentialité des données — ce que la plateforme fait réellement

Document interne source de vérité pour la politique de confidentialité
publiée. Reflété sur la page `/privacy` du frontend (`frontend/src/pages/Legal.tsx`).

## Ce qui est envoyé à des fournisseurs externes

| Donnée | Fournisseur | Quand | Finalité |
| --- | --- | --- | --- |
| Piste AUDIO de la vidéo | ElevenLabs (Scribe) | si `ELEVENLABS_API_KEY` configurée | transcription. Sinon: Whisper LOCAL, rien ne sort du serveur. |
| Transcript TEXTE horodaté | OpenRouter (modèle Gemini) | si `OPENROUTER_API_KEY` configurée | détection des moments forts (Clips) et nettoyage des hésitations. Repli local sans clé. |
| Extraits parlés (texte) | OpenRouter (modèle Gemini) | si B-roll IA activé | description des images à générer. |
| RIEN d'autre | — | — | la vidéo elle-même n'est JAMAIS envoyée à un fournisseur IA; le rendu est local (FFmpeg). |

L'utilisation des données par les fournisseurs pour l'entraînement dépend de
LEURS conditions (OpenRouter/Google, ElevenLabs) — le produit ne doit pas
promettre le contraire sans contrat adapté.

## Rétention sur nos serveurs

- Rendus terminés : `RETENTION_OUTPUT_DAYS` (défaut 14 j) puis purge automatique.
- Sources importées par URL : `RETENTION_SOURCE_DAYS` (défaut 7 j).
- Vidéos sources uploadées : `RETENTION_UPLOAD_DAYS` (défaut 30 j), puis
  retirées du tableau de bord.
- Fichiers des jobs échoués ou annulés : `RETENTION_FAILED_JOB_DAYS` (défaut 2 j).
- Lignes en base (historique des jobs, facturation) : conservées.

## Suppression par l'utilisateur

- `DELETE /videos/{id}` : supprime la vidéo source ET les fichiers rendus de
  tous ses jobs (les traitements en cours sont stoppés). Une ligne sans
  fichier est conservée (`deleted_at`) pour le décompte du quota mensuel.
- `DELETE /jobs/{id}` : supprime un traitement et tous ses fichiers.
- Les fichiers purgés/supprimés donnent l'erreur codifiée `FILE_EXPIRED`.

## Journalisation

Jamais journalisés : clés API, JWT, mots de passe, transcripts complets,
URLs signées. Journalisés : identifiants de requête/job, étapes, durées,
codes d'erreur.
