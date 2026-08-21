"""LLM provider model: presets, model discovery, key checks, model-string resolution.

Task 1.2 of the Aloth v2 roadmap. This module knows nothing about the agent
itself — it answers "which provider, which endpoint, which model string".
Integration into core.py/cli.py is done elsewhere.

Model strings follow PydanticAI 2.32 conventions (verified against the
installed pydantic_ai 2.32.1):
  * first-class providers (deepseek, openai, openrouter, ollama) use their
    native prefix, e.g. 'deepseek:deepseek-chat';
  * any other name is an arbitrary OpenAI-compatible provider and resolves to
    'openai:{model}'. A model string cannot carry a custom base URL, so for
    those the caller must also pass `OpenAIProvider(base_url=..., api_key=...)`
    as `model_provider` to the Agent (see pydantic_ai/providers/openai.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT = 10.0
"""HTTP timeout for discovery and key checks, in seconds."""


@dataclass(frozen=True)
class Provider:
    """An LLM provider: endpoint, auth, and default model."""

    name: str
    base_url: str
    default_model: str
    api_key: str | None = None
    env_var: str | None = None
    models: list[str] | None = None

    def key(self) -> str | None:
        """Return the API key: explicit value first, then env var, else None."""
        if self.api_key:
            return self.api_key
        if self.env_var:
            return os.environ.get(self.env_var)
        return None


PRESETS: dict[str, Provider] = {
    "deepseek": Provider(
        name="deepseek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        env_var="DEEPSEEK_API_KEY",
        models=["deepseek-chat", "deepseek-reasoner"],
    ),
    "openai": Provider(
        name="openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        env_var="OPENAI_API_KEY",
        models=["gpt-4o-mini", "gpt-4o", "o3-mini"],
    ),
    "openrouter": Provider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="openrouter/auto",
        env_var="OPENROUTER_API_KEY",
        models=None,  # каталог огромный — смотри discover_models()
    ),
    "ollama": Provider(
        name="ollama",
        base_url="http://localhost:11434",
        default_model="llama3.2",
        api_key=None,  # локальный сервер, ключ не нужен
        models=None,  # список моделей — через discover_models()
    ),
}


def get(name: str) -> Provider:
    """Return a preset provider by name.

    Raises:
        KeyError: with a Russian message listing available presets.
    """
    try:
        return PRESETS[name]
    except KeyError:
        raise KeyError(
            f"Неизвестный провайдер '{name}'. Доступны: {', '.join(PRESETS)}. "
            "Для произвольного OpenAI-compatible провайдера создайте "
            "Provider(name=..., base_url=..., default_model=...) сами."
        ) from None


def _get_models_response(
    base_url: str,
    api_key: str | None,
    client: httpx.Client | None = None,
) -> httpx.Response | None:
    """GET {base}/models (fallback {base}/v1/models); return first 2xx or None."""
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    for path in ("/models", "/v1/models"):
        try:
            r = (
                client.get(base + path, headers=headers)
                if client is not None
                else httpx.get(base + path, headers=headers, timeout=DEFAULT_TIMEOUT)
            )
            if r.status_code < 300:
                return r
        except httpx.HTTPError:
            continue
    return None


def discover_models(
    base_url: str,
    api_key: str | None = None,
    *,
    client: httpx.Client | None = None,
) -> list[str]:
    """Discover model IDs from an OpenAI-compatible /models endpoint.

    Returns an empty list on any failure — the caller decides how to handle it.

    Args:
        base_url: Provider base URL (trailing slash is fine).
        api_key: Optional key; sent as Bearer token when present.
        client: Optional httpx.Client (used by tests with MockTransport).
    """
    r = _get_models_response(base_url, api_key, client)
    if r is None:
        return []
    try:
        data = r.json().get("data", [])
        return [m["id"] for m in data if isinstance(m, dict) and "id" in m]
    except (ValueError, TypeError):
        return []


def test_key(
    base_url: str,
    api_key: str,
    *,
    client: httpx.Client | None = None,
) -> bool:
    """Verify an API key with a real request (GET /models); True on any 2xx."""
    return _get_models_response(base_url, api_key, client) is not None


def resolve(provider: Provider) -> tuple[str, str | None]:
    """Build (model_string, api_key) for PydanticAI 2.32.

    Preset names keep their native prefix ('deepseek:deepseek-chat');
    any other name is an arbitrary OpenAI-compatible provider → 'openai:{model}'.

    Note: for non-preset names (or any custom base_url) the model string alone
    is not enough — pydantic_ai 2.32 routes 'openai:{model}' to the default
    OpenAI endpoint. Pass the base_url through a provider object:
    `infer_model(model, provider_factory=lambda _: OpenAIProvider(base_url=..., api_key=...))`
    or `OpenAIChatModel(model_name, provider=OpenAIProvider(base_url=..., api_key=...))`.
    (DeepSeek/OpenRouter/Ollama are first-class providers with their own
    defaults, so their presets need no provider object unless the base_url
    is customized.)
    """
    prefix = provider.name if provider.name in PRESETS else "openai"
    return f"{prefix}:{provider.default_model}", provider.key()


def _self_check() -> None:
    """Offline checks: presets, resolve, URL building, discover/test on a fake server."""
    for var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        os.environ.pop(var, None)

    # Пресеты валидны
    assert PRESETS["deepseek"].base_url == "https://api.deepseek.com"
    assert PRESETS["openai"].base_url == "https://api.openai.com/v1"
    assert PRESETS["openrouter"].base_url == "https://openrouter.ai/api/v1"
    assert PRESETS["ollama"].base_url == "http://localhost:11434"
    assert PRESETS["ollama"].api_key is None

    # resolve: нативные префиксы, ключ из env_var
    assert resolve(PRESETS["deepseek"]) == ("deepseek:deepseek-chat", None)
    assert resolve(PRESETS["openai"])[0] == "openai:gpt-4o-mini"
    assert resolve(PRESETS["ollama"])[0] == "ollama:llama3.2"

    # resolve: произвольный OpenAI-compatible провайдер
    custom = Provider(
        name="my-llm",
        base_url="https://llm.example.com",
        default_model="my-model",
        env_var="MY_LLM_KEY",
    )
    assert resolve(custom) == ("openai:my-model", None)
    os.environ["MY_LLM_KEY"] = "k-test"
    assert resolve(custom) == ("openai:my-model", "k-test")
    del os.environ["MY_LLM_KEY"]

    # URL-построение + discover/test на фейковом сервере
    def primary(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer k"
        assert request.url.path == "/models"
        return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})

    ok_client = httpx.Client(transport=httpx.MockTransport(primary))
    assert discover_models("https://llm.example.com", "k", client=ok_client) == ["m1", "m2"]
    assert test_key("https://llm.example.com", "k", client=ok_client) is True

    # fallback: /models 404 → /v1/models (голый хост без /v1, со слэшем на конце)
    def fallback(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/models":
            return httpx.Response(404)
        return httpx.Response(200, json={"data": [{"id": "only-v1"}]})

    fb_client = httpx.Client(transport=httpx.MockTransport(fallback))
    assert discover_models("https://api.openai.com/", "k", client=fb_client) == ["only-v1"]

    # плохой ключ → 401 везде → пустой список / False
    denied = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401)))
    assert discover_models("https://llm.example.com", "bad", client=denied) == []
    assert test_key("https://llm.example.com", "bad", client=denied) is False

    print("providers ok")


if __name__ == "__main__":
    _self_check()
