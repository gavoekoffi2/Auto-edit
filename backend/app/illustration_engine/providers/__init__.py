"""Semantic intelligence providers and their fallback chain."""
from __future__ import annotations

import sys
from typing import List, Sequence

from .. import config
from .base import Refinement, SemanticProvider
from .chat_provider import ChatSemanticProvider
from .cloud_provider import CloudProvider
from .freellmapi_provider import FreeLLMAPIProvider
from .local_provider import LocalSemanticProvider

__all__ = [
    "Refinement", "SemanticProvider", "ChatSemanticProvider", "CloudProvider",
    "FreeLLMAPIProvider", "LocalSemanticProvider", "provider_chain",
    "resolve_provider",
]


def provider_chain(mode: str = None) -> List[SemanticProvider]:
    """Providers to try, in order, for an AI mode.

    Every chain ends on the local provider, so analysis always succeeds:

        cloud -> CloudProvider  -> FreeLLMAPI -> Local
        free  -> FreeLLMAPI     -> Local
        offline -> Local
    """
    mode = (mode or config.AI_MODE or "offline").strip().lower()
    if mode == "cloud":
        return [CloudProvider(), FreeLLMAPIProvider(), LocalSemanticProvider()]
    if mode == "free":
        return [FreeLLMAPIProvider(), LocalSemanticProvider()]
    return [LocalSemanticProvider()]


def resolve_provider(units: Sequence, mode: str = None):
    """Run the chain and return (refinements, provider_name).

    The first provider that is available *and* returns usable refinements
    wins; anything else falls through to the next one.
    """
    for provider in provider_chain(mode):
        if not provider.available():
            continue
        refinements = provider.refine(units)
        if refinements:
            return refinements, provider.name
        if provider.network:
            print(f"[illustration_engine] provider {provider.name} n'a rien "
                  f"renvoyé d'exploitable -> repli", file=sys.stderr)
    return [], "heuristic"
