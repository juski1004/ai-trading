"""무료 AI (구글 Gemini 무료 등급) 연결.

환경변수 GEMINI_API_KEY 가 없거나 호출이 실패하면 None 을 돌려주고,
그러면 THEO 는 규칙 기반 판정을 그대로 쓴다.
"""
from __future__ import annotations

import json
import os
import time
from typing import Protocol

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLM(Protocol):
    def ask_json(self, prompt: str) -> dict | None: ...


class GeminiClient:
    def __init__(self, api_key: str, model: str | None = None, min_interval_sec: float = 6.0):
        self.api_key = api_key
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.min_interval = min_interval_sec  # 무료 등급 분당 호출 한도 보호
        self._last = 0.0

    def ask_json(self, prompt: str) -> dict | None:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        try:
            r = requests.post(
                API.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
                },
                timeout=60,
            )
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:  # 한도 초과, 네트워크, 형식 오류 → 규칙 기반으로 대체
            print(f"[AI 연결 실패, 규칙 기반으로 진행] {type(e).__name__}: {str(e)[:120]}")
            return None


def from_env() -> LLM | None:
    key = os.getenv("GEMINI_API_KEY")
    return GeminiClient(key) if key else None
