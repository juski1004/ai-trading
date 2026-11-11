"""Gemini 이미지 만들기 (깡통 8편 등 AI 장면용). 사용: python tools/gemini_img.py <out폴더> "<프롬프트1> || <프롬프트2>" [모델들 쉼표]
키(GEMINI_API_KEY)는 환경변수로만 읽고 출력하지 않는다. 무료 한도가 막히면 다음 모델로 넘어간다. 결과: out/NN.png + out/log.txt"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODELS = ["gemini-3.1-flash-image", "gemini-2.5-flash-image", "gemini-3-pro-image"]


def gen(model: str, prompt: str, key: str) -> bytes | None:
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            if "inlineData" in p: return base64.b64decode(p["inlineData"]["data"])
    return None


def main() -> None:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    prompts = [p.strip() for p in sys.argv[2].split("||") if p.strip()]
    models = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else MODELS
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key: raise SystemExit("GEMINI_API_KEY 비밀값이 없습니다")
    log = []
    for i, pr in enumerate(prompts, 1):
        ok = False
        for m in models:
            try:
                img = gen(m, pr, key)
                if img:
                    (out / f"{i:02d}.png").write_bytes(img); log.append(f"{i:02d} OK {m}"); ok = True; break
                log.append(f"{i:02d} 빈 응답 {m}")
            except urllib.error.HTTPError as e:
                log.append(f"{i:02d} {m} HTTP {e.code} {e.read()[:120].decode('utf-8', 'ignore')}")
            except Exception as e:  # noqa: BLE001
                log.append(f"{i:02d} {m} {type(e).__name__}")
            time.sleep(2)
        if not ok: log.append(f"{i:02d} 실패")
        print(log[-1])
    (out / "log.txt").write_text("\n".join(log), encoding="utf-8")
    if not any(l.split()[1] == "OK" for l in log if len(l.split()) > 1): raise SystemExit("한 장도 못 만듦 (한도 확인)")


if __name__ == "__main__":
    main()
