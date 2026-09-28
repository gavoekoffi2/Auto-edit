"""Passerelle LLM: FreeLLMAPI (compatible OpenAI) d'abord, OpenRouter ensuite, règles sinon."""
import httpx
import pytest

from app.explainer import writer


class _Resp:
    def __init__(self, code, content):
        self.status_code = code; self._c = content; self.text = str(content); self.headers = {"X-Routed-Via": "groq/llama"}

    def json(self):
        return {"choices": [{"message": {"content": self._c}}]}


def _env(monkeypatch, base="", key="", orkey=""):
    monkeypatch.setenv("LLM_BASE_URL", base); monkeypatch.setenv("LLM_API_KEY", key); monkeypatch.setenv("OPENROUTER_API_KEY", orkey)


def test_no_gateway_means_rules(monkeypatch):
    _env(monkeypatch)
    assert writer.llm_endpoints() == [] and not writer.llm_available()
    with pytest.raises(RuntimeError):
        writer.chat("bonjour")


def test_gateway_first_then_openrouter(monkeypatch):
    _env(monkeypatch, base="http://freellmapi:3001/v1/", key="freellmapi-abc", orkey="sk-or")
    eps = writer.llm_endpoints()
    assert [e["name"] for e in eps] == ["passerelle", "openrouter"]
    assert eps[0]["url"] == "http://freellmapi:3001/v1/chat/completions" and eps[0]["model"] == "auto:smart"
    calls = []

    def fake_post(self, url, headers=None, json=None):
        calls.append((url, headers.get("Authorization"), json["model"]))
        return _Resp(503, "") if "freellmapi" in url else _Resp(200, "ok via openrouter")
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    assert writer.chat("x") == "ok via openrouter"
    assert calls[0][1] == "Bearer freellmapi-abc" and "openrouter" in calls[1][0]


def test_gateway_alone_is_enough(monkeypatch):
    _env(monkeypatch, base="http://localhost:3001/v1", key="freellmapi-k")
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, headers=None, json=None: _Resp(200, '{"beats": []}'))
    assert writer.llm_available() and writer.chat("x") == '{"beats": []}'
