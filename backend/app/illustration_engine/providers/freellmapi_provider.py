"""FreeLLMAPI provider — opt-in, never required.

FreeLLMAPI (https://github.com/tashfeenahmed/freellmapi) is MIT-licensed, but
**the licence of the proxy says nothing about the terms of the upstream
providers it routes to**. An aggregator being open source does not grant any
right to use the third-party services behind it commercially.

The engine therefore refuses to guess: this provider stays inert unless the
operator sets `FREELLM_BASE_URL` and `FREELLM_MODEL` explicitly, which is the
point at which they take responsibility for the upstream terms.
See docs/THIRD_PARTY_LICENSES.md.
"""
from __future__ import annotations

import os

from .. import config
from .chat_provider import ChatSemanticProvider


class FreeLLMAPIProvider(ChatSemanticProvider):
    name = "freellmapi"

    def __init__(self, base_url: str = "", model: str = "",
                 timeout: float = None):
        super().__init__(
            base_url=base_url or config.FREELLM_BASE_URL,
            model=model or config.FREELLM_MODEL,
            api_key=os.environ.get("FREELLM_API_KEY", ""),
            timeout=config.FREELLM_TIMEOUT if timeout is None else timeout,
        )

    def available(self) -> bool:
        # Both must be configured: a base URL without a model, or the reverse,
        # is a half-configured deployment, not an invitation to pick defaults.
        return bool(self.base_url and self.model)
