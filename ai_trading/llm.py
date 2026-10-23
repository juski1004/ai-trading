"""무료 AI (구글 Gemini 무료 등급) 연결.

환경변수 GEMINI_API_KEY 가 없거나 호출이 실패하면 None 을 돌려주고,
그러면 THEO 는 규칙 기반 판정을 그대로 쓴다.

구글이 모델 이름을 자주 바꾸고 옛 이름을 없애서(404), 모델은 이렇게 고른다.
  1. GEMINI_MODEL 환경변수가 있으면 그것
  2. 없으면 이 키로 쓸 수 있는 모델 목록을 받아 가장 최신 'flash' 모델
모델을 못 쓰게 되면(404) 한 번 다시 고르고, 그래도 안 되면 이번 실행에서는 AI를 끈다.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Protocol

import requests

BASE = "https://generativelanguage.googleapis.com/v1beta"
SKIP = ("image", "tts", "audio", "live", "embedding", "vision", "learnlm", "robotics", "computer")


class LLM(Protocol):
    def ask_json(self, prompt: str) -> dict | None: ...


def pick_model(models: list[dict]) -> str | None:
    """generateContent 를 지원하는 모델 중 가장 최신 flash (정식판 우선, lite 는 뒤로)."""
    cands = []
    for m in models:
        name = m.get("name", "").removeprefix("models/")
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if not name.startswith("gemini") or "flash" not in name or any(s in name for s in SKIP):
            continue
        ver = tuple(int(x) for x in re.findall(r"\d+", name.split("-")[1])) if "-" in name else (0,)
        preview = any(s in name for s in ("preview", "exp"))
        cands.append(((not preview, "lite" not in name, "latest" in name, ver), name))
    return max(cands)[1] if cands else None


class GeminiClient:
    def __init__(self, api_key: str, model: str | None = None, min_interval_sec: float = 6.0):
        self.api_key = api_key
        self.model = model or os.getenv("GEMINI_MODEL") or None
        self.min_interval = min_interval_sec  # 무료 등급 분당 호출 한도 보호
        self._last = 0.0
        self._rediscovered = False
        self.disabled = False

    def _discover(self) -> str | None:
        try:
            r = requests.get(f"{BASE}/models", headers={"x-goog-api-key": self.api_key},
                             params={"pageSize": 200}, timeout=30)
            r.raise_for_status()
            name = pick_model(r.json().get("models", []))
            print(f"[AI] 사용할 Gemini 모델: {name}")
            return name
        except Exception as e:
            print(f"[AI 모델 목록 실패] {type(e).__name__}: {str(e)[:120]}")
            return None

    def ask_json(self, prompt: str) -> dict | None:
        if self.disabled:
            return None
        if not self.model:
            self.model = self._discover()
            if not self.model:
                self.disabled = True
                return None
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        try:
            r = requests.post(
                f"{BASE}/models/{self.model}:generateContent",
                headers={"x-goog-api-key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
                },
                timeout=60,
            )
            if r.status_code == 404:  # 모델이 없어짐 → 한 번 다시 고르기
                print(f"[AI] 모델 '{self.model}' 을 쓸 수 없음 (404)")
                if self._rediscovered:
                    self.disabled = True
                    return None
                self._rediscovered = True
                self.model = self._discover()
                return self.ask_json(prompt) if self.model else self._off()
            if r.status_code in (429, 500, 503) and getattr(self, "_retry", 0) < 2:  # 분당 한도·서버 바쁨 → 쉬었다가 다시
                self._retry = getattr(self, "_retry", 0) + 1
                wait = 25 * self._retry
                print(f"[AI] {r.status_code} 응답, {wait}초 쉬고 다시 시도 ({self._retry}/2)")
                time.sleep(wait)
                try:
                    return self.ask_json(prompt)
                finally:
                    self._retry = 0
            if r.status_code in (401, 403):  # 키 문제는 다시 해 봐야 소용없음
                print(f"[AI] 키가 거부됨 ({r.status_code}), 이번 실행은 규칙 기반으로 진행")
                return self._off()
            if r.status_code == 429:  # 쉬었다 다시 해도 한도 초과 → 오늘 무료 한도 소진. 계속 기다리면 실행이 시간 초과로 끝남
                print("[AI] Gemini 무료 한도 소진, 이번 실행에서는 더 부르지 않음")
                return self._off()
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:  # 한도 초과, 네트워크, 형식 오류 → 규칙 기반으로 대체
            print(f"[AI 연결 실패, 규칙 기반으로 진행] {type(e).__name__}: {str(e)[:120]}")
            return None

    def _off(self) -> None:
        self.disabled = True
        return None


class OpenAICompatClient:
    """OpenAI 형식 API (Groq 무료 등급, xAI Grok). 모델은 목록에서 고른다."""

    def __init__(self, name: str, base: str, api_key: str, prefer: tuple[str, ...], min_interval_sec: float = 3.0):
        self.name, self.base, self.api_key, self.prefer = name, base, api_key, prefer
        self.model = os.getenv(f"{name.upper()}_MODEL") or None
        self.min_interval, self._last, self.disabled = min_interval_sec, 0.0, False

    def _discover(self) -> str | None:
        try:
            r = requests.get(f"{self.base}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=30)
            r.raise_for_status()
            ids = [m.get("id", "") for m in r.json().get("data", [])]
            ids = [i for i in ids if not any(s in i for s in ("whisper", "tts", "guard", "embed", "image", "vision", "audio"))]
            for pref in self.prefer:
                hit = [i for i in ids if pref in i]
                if hit:
                    print(f"[AI] {self.name} 모델: {sorted(hit)[-1]}")
                    return sorted(hit)[-1]
            return ids[0] if ids else None
        except Exception as e:
            print(f"[AI {self.name} 모델 목록 실패] {type(e).__name__}: {str(e)[:120]}")
            return None

    def ask_json(self, prompt: str) -> dict | None:
        if self.disabled:
            return None
        if not self.model:
            self.model = self._discover()
            if not self.model:
                self.disabled = True
                return None
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        for attempt in range(3):
            try:
                r = requests.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=60,
                                  json={"model": self.model, "temperature": 0.2, "response_format": {"type": "json_object"},
                                        "messages": [{"role": "system", "content": "Answer only with one JSON object. 한국어로 답한다."},
                                                     {"role": "user", "content": prompt}]})
                if r.status_code in (401, 403):
                    print(f"[AI] {self.name} 키가 거부됨 ({r.status_code})")
                    self.disabled = True
                    return None
                if r.status_code in (429, 500, 503) and attempt < 2:
                    time.sleep(20 * (attempt + 1))
                    continue
                if r.status_code == 400:  # 요청 형식 거절은 다시 해도 같음 → 이유를 남기고 이번 실행에서는 끄기
                    print(f"[AI] {self.name} 요청 거절 (400): {r.text[:300]}")
                    self.disabled = True
                    return None
                if r.status_code == 429:  # 다시 해도 한도 초과 → 이번 실행에서는 끄기
                    print(f"[AI] {self.name} 무료 한도 소진, 이번 실행에서는 더 부르지 않음")
                    self.disabled = True
                    return None
                r.raise_for_status()
                return json.loads(r.json()["choices"][0]["message"]["content"])
            except Exception as e:
                print(f"[AI {self.name} 실패] {type(e).__name__}: {str(e)[:120]}")
                return None
        return None


class FallbackLLM:
    """앞에서부터 차례로 시도: Gemini → Groq(무료) → Grok(유료)."""

    def __init__(self, clients: list):
        self.clients = clients
        self.last_used: str | None = None

    def ask_json(self, prompt: str) -> dict | None:
        for c in self.clients:
            ans = c.ask_json(prompt)
            if ans is not None:
                self.last_used = getattr(c, "name", type(c).__name__)
                return ans
        return None


def from_env() -> LLM | None:
    clients = []
    if os.getenv("GEMINI_API_KEY"):
        g = GeminiClient(os.environ["GEMINI_API_KEY"])
        g.name = "Gemini"
        clients.append(g)
    if os.getenv("GROQ_API_KEY"):
        clients.append(OpenAICompatClient("Groq", "https://api.groq.com/openai/v1", os.environ["GROQ_API_KEY"],
                                          ("llama-3.3-70b", "llama-3.1-70b", "70b", "llama")))
    if os.getenv("XAI_API_KEY"):
        clients.append(OpenAICompatClient("Grok", "https://api.x.ai/v1", os.environ["XAI_API_KEY"],
                                          ("grok-3-mini", "mini", "fast", "grok")))
    if not clients:
        return None
    return clients[0] if len(clients) == 1 else FallbackLLM(clients)


def check() -> list[str]:
    """등록된 AI마다 짧은 질문을 보내 응답이 오는지 확인 (키 값은 출력하지 않음)."""
    out = []
    for name, env in (("Gemini", "GEMINI_API_KEY"), ("Groq", "GROQ_API_KEY"), ("Grok", "XAI_API_KEY")):
        key = os.getenv(env)
        if not key:
            out.append(f"{name}: 키 없음")
            continue
        if name == "Gemini":
            c = GeminiClient(key)
        elif name == "Groq":
            c = OpenAICompatClient("Groq", "https://api.groq.com/openai/v1", key, ("llama-3.3-70b", "llama-3.1-70b", "70b", "llama"))
        else:
            c = OpenAICompatClient("Grok", "https://api.x.ai/v1", key, ("grok-3-mini", "mini", "fast", "grok"))
        ans = c.ask_json('JSON으로만 답하라: {"ok": true, "word": "안녕"}')
        out.append(f"{name}: {'정상' if isinstance(ans, dict) else '실패'} (모델 {getattr(c, 'model', None)})")
    return out


if __name__ == "__main__":
    print("\n".join(check()))
