"""ConceptDetector — what is this passage actually about?

Concepts drive the icon choice, the element labels and the repeat detection.
They are extracted with TF-over-the-video weighting plus a domain lexicon, so
a word that the speaker keeps coming back to outranks a one-off noun.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence

from . import lexicon as lx

try:  # reuse the montage engine's curated stopword list when available
    from ...autoedit_engine import config as _engine_config
    _BASE_STOPWORDS = {lx.fold(w) for w in getattr(_engine_config, "STOPWORDS", ())}
    _BASE_FILLERS = {lx.fold(w) for w in getattr(_engine_config, "FILLERS", ())}
except Exception:  # noqa: BLE001 - the engine must stand alone too
    _BASE_STOPWORDS, _BASE_FILLERS = set(), set()

_EXTRA_STOPWORDS = {
    "etre", "avoir", "faire", "aller", "dire", "voir", "savoir", "pouvoir",
    "vouloir", "devoir", "falloir", "vraiment", "beaucoup", "toujours",
    "jamais", "aussi", "comme", "tout", "tous", "toute", "toutes", "meme",
    "chose", "choses", "gens", "personne", "truc", "fois", "peu", "plus",
    "moins", "tres", "bien", "juste", "petit", "grand", "bon", "bonne",
    "video", "aujourd", "hui", "cette", "leurs", "notre", "votre",
    "thing", "things", "people", "really", "very", "just", "make", "made",
    "going", "want", "need", "know", "think", "like", "good", "great",
    "today", "video", "about", "because", "there", "their", "these", "those",
    "what", "when", "where", "which", "will", "would", "could", "should",
    "have", "that", "this", "with", "from", "your", "you", "they", "them",
    # Adverbs and interrogatives read as emphasis, never as subject matter.
    "absolument", "completement", "totalement", "simplement", "exactement",
    "forcement", "evidemment", "rapidement", "facilement", "directement",
    "franchement", "carrement", "tellement", "vachement", "clairement",
    "comment", "pourquoi", "quand", "combien", "lequel", "laquelle",
    # Auxiliaries and modals: they introduce the subject, they are not it.
    "faut", "faudra", "veut", "veux", "peut", "peux", "doit", "dois",
    "devez", "allez", "vient", "prend", "fait", "dit", "voit", "sait",
    "envoie", "donne", "met", "vais", "suis", "sont", "etre", "avoir",
    "surtout", "plutot", "ensuite", "encore", "deja", "alors", "ainsi",
    "absolutely", "completely", "simply", "exactly", "obviously", "quickly",
    "easily", "directly", "honestly", "how", "why", "when", "much", "many",
}

# Ordinals and sequence markers signal structure; they are never the subject
# of the passage, so they must not end up in a scene title.
_STRUCTURAL = {lx.fold(w) for w in
               tuple(lx.ORDINALS) + lx.SEQUENCE_MARKERS + lx.STEP_WORDS}
_STRUCTURAL |= {w for phrase in _STRUCTURAL for w in phrase.split()}

STOPWORDS = _BASE_STOPWORDS | _BASE_FILLERS | _EXTRA_STOPWORDS | _STRUCTURAL

# Domain vocabulary that CutForge's audience actually talks about. A hit here
# is worth more than raw frequency: it names something drawable.
DOMAIN_CONCEPTS: Dict[str, Sequence[str]] = {
    "mobile_money": ("mobile money", "momo", "orange money", "wave", "mtn money",
                     "transfert", "recharge", "portefeuille", "wallet"),
    "ecommerce": ("ecommerce", "e-commerce", "boutique", "shop", "store",
                  "panier", "commande", "produit", "catalogue", "vente"),
    "delivery": ("livraison", "livreur", "colis", "expedition", "transport",
                 "delivery", "shipping", "parcel"),
    "customer": ("client", "clients", "acheteur", "consommateur", "customer",
                 "buyer", "audience", "prospect"),
    "seller": ("vendeur", "vendeuse", "commercant", "marchand", "seller",
               "merchant", "entrepreneur"),
    "phone": ("telephone", "smartphone", "mobile", "portable", "phone", "app",
              "application"),
    "social": ("reseaux sociaux", "instagram", "tiktok", "facebook", "whatsapp",
               "social", "followers", "abonnes", "communaute"),
    "business": ("entreprise", "business", "societe", "startup", "marque",
                 "chiffre d'affaires", "benefice", "marge", "revenue"),
    "ai": ("intelligence artificielle", "ia", " ai ", "chatgpt", "modele",
           "algorithme", "automatisation", "machine learning"),
    "africa": ("afrique", "africain", "africaine", "abidjan", "dakar", "lagos",
               "accra", "cotonou", "douala", "kinshasa", "africa"),
    "education": ("formation", "cours", "apprendre", "etudiant", "ecole",
                  "education", "learning", "training", "student"),
    "agriculture": ("agriculture", "agricole", "champ", "recolte", "cacao",
                    "culture", "ferme", "farming", "harvest"),
    "finance": ("banque", "credit", "epargne", "investissement", "budget",
                "finance", "argent", "capital", "prêt", "pret", "loan"),
    "traffic": ("trafic", "visiteurs", "audience", "publicite", "ads",
                "traffic", "campagne", "conversion"),
    "growth": ("croissance", "augmenter", "scaler", "developper", "growth",
               "scale", "progression"),
    "time": ("temps", "heure", "jour", "semaine", "mois", "delai", "rapide",
             "time", "hour", "week", "month", "deadline"),
    "risk": ("risque", "erreur", "piege", "danger", "arnaque", "perte",
             "risk", "mistake", "scam", "loss"),
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'\-]{2,}")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(lx.fold(text))


def content_tokens(text: str) -> List[str]:
    return [t for t in tokenize(text)
            if t not in STOPWORDS and len(t) > 2 and not t.isdigit()]


class ConceptDetector:
    """Ranks the concepts of each unit against the whole video."""

    def __init__(self, corpus: Iterable[str] = ()):
        self.doc_counts: Counter = Counter()
        self.n_docs = 1
        texts = list(corpus)
        if texts:
            self.fit(texts)

    def fit(self, texts: Sequence[str]) -> "ConceptDetector":
        self.doc_counts = Counter()
        for text in texts:
            self.doc_counts.update(set(content_tokens(text)))
        self.n_docs = max(1, len(texts))
        return self

    # ------------------------------------------------------------------ #
    def domains(self, text: str) -> List[str]:
        """Domain labels this passage touches, most specific first."""
        folded = " %s " % lx.fold(text)
        hits: List[tuple] = []
        for domain, terms in DOMAIN_CONCEPTS.items():
            score = sum(1 for term in terms if term in folded)
            if score:
                hits.append((score, domain))
        hits.sort(reverse=True)
        return [domain for _score, domain in hits]

    def concepts(self, text: str, limit: int = 5) -> List[str]:
        """Salient concept tokens, weighted by how central they are overall."""
        tokens = content_tokens(text)
        if not tokens:
            return []
        local = Counter(tokens)
        scored = []
        for token, count in local.items():
            # Recurring across the video = the video's subject; boost it.
            centrality = self.doc_counts.get(token, 0) / float(self.n_docs or 1)
            scored.append((count * (1.0 + min(centrality, 1.0)) + 0.35 * len(token) / 10.0,
                           token))
        scored.sort(reverse=True)
        picked = [token for _score, token in scored[:limit]]
        # Restore the order the speaker used — "PRODUIT TRAFIC LIVRAISON"
        # reads like the sentence; ranked order reads like a word cloud.
        folded_text = lx.fold(text)
        return sorted(picked, key=lambda tok: folded_text.find(tok))

    # Conjugated verbs and infinitives make a poor title: "PERDAIENT
    # ENCAISSER" says nothing, while the nouns around them name the subject.
    # Length guards keep real nouns ("argent", "avenir") out of the net.
    _CONJUGATED = ("aient", "erent", "ames", "ates", "ions", "iez", "ais",
                   "ait", "ant", "ez")
    _INFINITIVE = ("er", "ir", "re")

    def _looks_like_verb(self, token: str) -> bool:
        if len(token) < 6:
            return False
        if token.endswith(self._CONJUGATED):
            return True
        # Infinitives only from 7 characters, so "argent" and "avenir" survive.
        return len(token) >= 7 and token.endswith(self._INFINITIVE)

    def headline(self, text: str, max_words: int = 4, max_chars: int = 26) -> str:
        """Short title for the scene, built from its strongest concepts.

        Truncation happens on a word boundary: a title ending in "TRA" reads
        as a rendering bug, not as a title.
        """
        # Ask for more than needed, then drop the verb forms: filtering after
        # ranking keeps the best remaining nouns instead of the leftovers.
        ranked = self.concepts(text, limit=max_words + 3)
        picked = [t for t in ranked if not self._looks_like_verb(t)][:max_words]
        if not picked:
            picked = ranked[:max_words]
        if not picked:
            picked = [w for w in (text or "").split() if len(w) > 2][:max_words]
        out: list = []
        for word in picked[:max_words]:
            candidate = " ".join(out + [word])
            if out and len(candidate) > max_chars:
                break
            out.append(word)
        return " ".join(out).upper()[:max_chars].strip()

    def concreteness(self, text: str) -> float:
        """0..1 — how drawable this passage is.

        Domain hits and concrete nouns mean there is something to put on
        screen; an abstract sentence full of verbs has nothing to show.
        """
        domains = self.domains(text)
        tokens = content_tokens(text)
        if not tokens:
            return 0.0
        domain_score = min(1.0, len(domains) / 3.0)
        density = min(1.0, len(set(tokens)) / 12.0)
        return round(0.6 * domain_score + 0.4 * density, 3)
