import json

import pytest

from ai_trading import llm
from ai_trading.llm import GeminiClient, pick_model

M = lambda name, gen=True: {"name": f"models/{name}", "supportedGenerationMethods": ["generateContent"] if gen else ["embedContent"]}


def test_pick_model_prefers_newest_stable_flash():
    models = [M("gemini-2.5-flash"), M("gemini-3.0-flash"), M("gemini-3.5-flash-preview-09"), M("gemini-3.0-flash-lite"),
              M("gemini-3.0-pro"), M("gemini-3.0-flash-image"), M("text-embedding-004", gen=False), M("gemma-3-27b-it")]
    assert pick_model(models) == "gemini-3.0-flash"
    assert pick_model([M("gemini-3.5-flash-preview-09")]) == "gemini-3.5-flash-preview-09"
    assert pick_model([M("gemini-3.0-pro")]) is None


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def ok(answer):
    return Resp(200, {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]})


@pytest.fixture
def fake(monkeypatch):
    calls = {"get": 0, "post": []}
    state = {"models": [M("gemini-9.0-flash")], "posts": {}}

    def get(url, **kw):
        calls["get"] += 1
        return Resp(200, {"models": state["models"]})

    def post(url, **kw):
        model = url.split("/models/")[1].split(":")[0]
        calls["post"].append(model)
        return state["posts"].get(model, Resp(404, {}))

    monkeypatch.setattr(llm.requests, "get", get)
    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    return calls, state


def test_discovers_model_when_none_set(fake):
    calls, state = fake
    state["posts"]["gemini-9.0-flash"] = ok({"action": "HOLD"})
    c = GeminiClient("k", min_interval_sec=0)
    assert c.ask_json("p") == {"action": "HOLD"} and c.model == "gemini-9.0-flash"
    assert c.ask_json("p") == {"action": "HOLD"} and calls["get"] == 1  # 목록은 한 번만


def test_retired_model_rediscovers_once(fake):
    calls, state = fake
    state["posts"]["gemini-9.0-flash"] = ok({"x": 1})
    c = GeminiClient("k", model="gemini-2.5-flash", min_interval_sec=0)
    assert c.ask_json("p") == {"x": 1}
    assert calls["post"] == ["gemini-2.5-flash", "gemini-9.0-flash"]


def test_gives_up_quietly_after_second_404(fake):
    calls, state = fake  # 목록에 있는 모델도 404
    c = GeminiClient("k", model="gemini-2.5-flash", min_interval_sec=0)
    assert c.ask_json("p") is None and c.disabled
    n = len(calls["post"])
    assert c.ask_json("p") is None and len(calls["post"]) == n  # 더 이상 호출하지 않음


def test_bad_key_disables(fake):
    calls, state = fake
    state["posts"]["gemini-9.0-flash"] = Resp(403, {})
    c = GeminiClient("k", min_interval_sec=0)
    assert c.ask_json("p") is None and c.disabled


def test_fallback_uses_next_ai_when_first_fails():
    from ai_trading.llm import FallbackLLM

    class Dead:
        name = "Gemini"
        def ask_json(self, p): return None

    class Alive:
        name = "Groq"
        def ask_json(self, p): return {"ok": 1}

    f = FallbackLLM([Dead(), Alive()])
    assert f.ask_json("x") == {"ok": 1} and f.last_used == "Groq"
    assert FallbackLLM([Dead()]).ask_json("x") is None


def test_from_env_builds_chain(monkeypatch):
    from ai_trading import llm
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert llm.from_env() is None
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert isinstance(llm.from_env(), llm.OpenAICompatClient)
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert isinstance(llm.from_env(), llm.FallbackLLM)


def test_quota_exhausted_disables_for_rest_of_run(fake, monkeypatch):
    calls, state = fake
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    state["posts"]["gemini-9.0-flash"] = Resp(429, {})
    c = GeminiClient("k", min_interval_sec=0)
    assert c.ask_json("p") is None and c.disabled
    n = len(calls["post"])
    assert n == 3  # 처음 1번 + 쉬었다가 2번
    assert c.ask_json("p") is None and len(calls["post"]) == n  # 다음 종목부터는 기다리지 않음


def test_groq_quota_exhausted_disables(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    posts = []
    monkeypatch.setattr(llm.requests, "post", lambda url, **kw: posts.append(url) or Resp(429, {}))
    c = llm.OpenAICompatClient("Groq", "https://x", "k", ("llama",), min_interval_sec=0)
    c.model = "llama"
    assert c.ask_json("p") is None and c.disabled and len(posts) == 3
    assert c.ask_json("p") is None and len(posts) == 3
