"""Cloud provider — any OpenAI-compatible endpoint the operator configures.

No vendor is hardcoded. The endpoint, the model and the name of the
environment variable holding the key all come from configuration, so switching
provider is a deployment change and never a code change.
"""
from __future__ import annotations

import os

from .. import config
from .chat_provider import ChatSemanticProvider


class CloudProvider(ChatSemanticProvider):
    name = "cloud"

    def __init__(self, base_url: str = "", model: str = "",
                 api_key_env: str = "", timeout: float = None):
        env_name = api_key_env or config.CLOUD_API_KEY_ENV
        super().__init__(
            base_url=base_url or config.CLOUD_BASE_URL,
            model=model or config.CLOUD_MODEL,
            api_key=os.environ.get(env_name, ""),
            timeout=config.CLOUD_TIMEOUT if timeout is None else timeout,
        )
        self.api_key_env = env_name

    def available(self) -> bool:
        return bool(self.base_url and self.model and self.api_key)
