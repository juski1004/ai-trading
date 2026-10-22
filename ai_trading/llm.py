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
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:  # 한도 초과, 네트워크, 형식 오류 → 규칙 기반으로 대체
            print(f"[AI 연결 실패, 규칙 기반으로 진행] {type(e).__name__}: {str(e)[:120]}")
            return None

    def _off(self) -> None:
        self.disabled = True
        return None


def from_env() -> LLM | None:
    key = os.getenv("GEMINI_API_KEY")
    return GeminiClient(key) if key else None
