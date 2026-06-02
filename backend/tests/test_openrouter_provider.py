"""Tests d'integration du provider OpenRouter, avec mock httpx.Client.

Couvre:
  - succes via /images/generations (b64_json)
  - succes via /images/generations (url)
  - fallback vers /chat/completions (data: URL inline)
  - erreur quand la cle API est absente
  - erreur quand les deux endpoints renvoient 400
"""
from __future__ import annotations

import base64
from typing import Any
import pytest

from app.processing.providers.openrouter_image import (
    OpenRouterError,
    OpenRouterImageProvider,
)


PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)


class _MockResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._json


class _MockClient:
    """Minimal stand-in for httpx.Client supporting context manager + post."""

    def __init__(self, posts: list[_MockResponse]):
        self._responses = list(posts)
        self.calls: list[tuple[str, dict | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, headers=None, json=None):
        self.calls.append((url, json))
        if not self._responses:
            raise RuntimeError("no mock response left")
        return self._responses.pop(0)

    def get(self, url):  # pragma: no cover - unused here
        raise RuntimeError("not implemented")


def _install_mock(monkeypatch, responses: list[_MockResponse]) -> _MockClient:
    client = _MockClient(responses)
    monkeypatch.setattr(
        "app.processing.providers.openrouter_image.httpx.Client",
        lambda *a, **kw: client,
    )
    return client


def test_images_endpoint_b64_success(monkeypatch):
    monkeypatch.setattr(
        "app.processing.providers.openrouter_image.settings.OPENROUTER_API_KEY",
        "fake-key",
        raising=False,
    )
    b64 = base64.b64encode(PNG_1PX).decode()
    _install_mock(monkeypatch, [_MockResponse(200, {"data": [{"b64_json": b64}]})])

    provider = OpenRouterImageProvider(api_key="fake-key", model="m1")
    image = provider.generate(prompt="hello", aspect_ratio="9:16")

    assert image.bytes == PNG_1PX
    assert image.url is None
    assert image.provider == "openrouter"
    assert image.model == "m1"


def test_images_endpoint_url_success(monkeypatch):
    _install_mock(monkeypatch, [_MockResponse(200, {"data": [{"url": "https://x/img.png"}]})])
    provider = OpenRouterImageProvider(api_key="fake-key", model="m1")
    image = provider.generate(prompt="hello")
    assert image.url == "https://x/img.png"
    assert image.bytes is None


def test_falls_back_to_chat_endpoint_when_images_returns_404(monkeypatch):
    b64 = base64.b64encode(PNG_1PX).decode()
    data_url = f"data:image/png;base64,{b64}"
    _install_mock(
        monkeypatch,
        [
            _MockResponse(404, text="not found"),  # images endpoint indispo
            _MockResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "image_url", "image_url": {"url": data_url}}
                                ]
                            }
                        }
                    ]
                },
            ),
        ],
    )
    provider = OpenRouterImageProvider(api_key="fake-key", model="m1")
    image = provider.generate(prompt="hello")
    assert image.bytes == PNG_1PX


def test_chat_endpoint_extracts_from_message_images(monkeypatch):
    _install_mock(
        monkeypatch,
        [
            _MockResponse(404, text="not found"),
            _MockResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "images": [{"url": "https://x/y.png"}],
                                "content": "",
                            }
                        }
                    ]
                },
            ),
        ],
    )
    provider = OpenRouterImageProvider(api_key="fake-key", model="m1")
    image = provider.generate(prompt="hello")
    assert image.url == "https://x/y.png"


def test_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(
        "app.processing.providers.openrouter_image.settings.OPENROUTER_API_KEY",
        None,
        raising=False,
    )
    # On force aussi le constructor à ne pas recevoir de cle
    provider = OpenRouterImageProvider(api_key=None, model="m1")
    with pytest.raises(OpenRouterError):
        provider.generate(prompt="hello")


def test_both_endpoints_fail_raises(monkeypatch):
    _install_mock(
        monkeypatch,
        [
            _MockResponse(500, text="boom1"),
            _MockResponse(500, text="boom2"),
        ],
    )
    provider = OpenRouterImageProvider(api_key="fake-key", model="m1")
    with pytest.raises(OpenRouterError):
        provider.generate(prompt="hello")


def test_size_mapping():
    assert OpenRouterImageProvider._size_for("9:16") == "1024x1792"
    assert OpenRouterImageProvider._size_for("16:9") == "1792x1024"
    assert OpenRouterImageProvider._size_for("1:1") == "1024x1024"
    # Defaut
    assert OpenRouterImageProvider._size_for("unknown") == "1024x1024"
