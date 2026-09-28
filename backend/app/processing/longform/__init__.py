"""Moteur « YouTube long » — montage automatique des vidéos longues (16:9).

Porté de la méthode `youtube-clean` et adapté à CutForge / aux créateurs
francophones :

  1. transcription mot-à-mot (ElevenLabs Scribe, repli Whisper) ;
  2. coupe de la voix UNE fois : la dernière prise gagne, répétitions,
     faux départs, bégaiements et silences retirés, points de coupe posés
     dans les creux d'énergie (RMS) ;
  3. assemblage image + son 1:1 (un seul encodeur, une horloge 30 i/s,
     un buffer audio sans trou) — pas de dérive de synchro labiale même
     sur une heure de vidéo ;
  4. chapitres YouTube (titres IA si clé, sinon mots-clés) ;
  5. habillage : zooms alternés qui masquent les coupes, sous-titres FR
     karaoké, mots-clés animés, cartes chapitre plein écran ;
  6. son : effets sonores liés à chaque visuel, musique en fond avec
     ducking, loudness −14 LUFS ;
  7. vérifications signal (synchro, durée, loudness) dans le rapport.

Point d'entrée : :func:`app.processing.longform.pipeline.run_longform`.
"""

LONGFORM_MODES = ("youtube_long", "youtube_long_sobre", "youtube_long_energie")
