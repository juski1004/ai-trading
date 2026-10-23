"""본부장 브리핑을 미리 녹음해 web/data/brief/ 에 둔다 (화면의 '읽어주기'가 먼저 이 파일을 튼다).

    python -m ai_trading.brief_audio /tmp/brief.html web/data/brief

/tmp/brief.html 은 헤드리스 크롬으로 '?view=brieftext' 를 열어 저장한 것 (안에 <pre id="briefjson">).
여자(f, 정서연) · 남자(m, 백승현) 두 목소리를 장마다 만든다.

비상장치: 아래 순서로 시도하고, 한도 초과·오류가 나면 그 실행 동안 그 도구는 끄고 다음 도구로 넘어간다.
  1) 일레븐랩스   ELEVENLABS_API_KEY  (무료 월 1만 자 — 금방 차므로 차면 자동으로 2번으로)
  2) 구글 클라우드 TTS  GOOGLE_TTS_API_KEY  (Wavenet, 무료 월 100만 자)
  3) 엣지(마이크로소프트) 뉴럴 음성  키 필요 없음  — 선희(여)·인준(남) 아나운서 톤
  4) 구글 번역 음성(gTTS)  키 필요 없음  — 여자 목소리 하나뿐
전부 실패하면 그 목소리는 비워 두고, 화면은 기기 목소리로 읽는다.
"""
import asyncio
import base64
import html
import json
import os
import re
import sys
from pathlib import Path

import requests

VOICES = {
    "f": {"eleven": os.getenv("ELEVEN_VOICE_F", "21m00Tcm4TlvDq8ikWAM"), "google": "ko-KR-Wavenet-A", "edge": "ko-KR-SunHiNeural"},
    "m": {"eleven": os.getenv("ELEVEN_VOICE_M", "pNInz6obpgDQGcFmaJgB"), "google": "ko-KR-Wavenet-C", "edge": "ko-KR-InJoonNeural"},
}


class Quota(Exception):
    """한도 초과·키 문제 → 이번 실행에서 이 도구는 그만 쓴다."""


def eleven(text, g):
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise Quota("키 없음")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICES[g]['eleven']}",
        headers={"xi-api-key": key, "accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2",
              "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "speed": 1.15}},
        timeout=120,
    )
    if r.status_code in (401, 402, 403, 429) or "quota" in r.text[:300].lower():
        raise Quota(f"{r.status_code} {r.text[:200]}")
    r.raise_for_status()
    return r.content


def google(text, g):
    key = os.getenv("GOOGLE_TTS_API_KEY")
    if not key:
        raise Quota("키 없음")
    r = requests.post(
        f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
        json={"input": {"text": text}, "voice": {"languageCode": "ko-KR", "name": VOICES[g]["google"]},
              "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.3}},
        timeout=120,
    )
    if r.status_code in (400, 401, 403, 429):
        raise Quota(f"{r.status_code} {r.text[:200]}")
    r.raise_for_status()
    return base64.b64decode(r.json()["audioContent"])


def edge(text, g):
    import edge_tts  # pip install edge-tts

    async def run():
        out = b""
        async for c in edge_tts.Communicate(text, VOICES[g]["edge"], rate="+30%").stream():
            if c["type"] == "audio":
                out += c["data"]
        return out

    data = asyncio.run(run())
    if not data:
        raise RuntimeError("빈 음성")
    return data


def gtts(text, g):
    from io import BytesIO

    from gtts import gTTS  # pip install gTTS

    buf = BytesIO()
    gTTS(text, lang="ko").write_to_fp(buf)
    return buf.getvalue()


ENGINES = [("elevenlabs", eleven), ("google", google), ("edge", edge), ("gtts", gtts)]


def read_steps(src):
    raw = Path(src).read_text(encoding="utf-8", errors="replace")
    m = re.search(r'<pre id="briefjson"[^>]*>(.*?)</pre>', raw, re.S)
    if not m:
        sys.exit("브리핑 글을 찾지 못했습니다 (?view=brieftext 화면이 안 열림)")
    return json.loads(html.unescape(m.group(1)))


def main(src, out):
    data = read_steps(src)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.mp3"):
        f.unlink()
    dead, used = set(), {}
    for g in ("f", "m"):
        # 한 목소리의 모든 장은 같은 도구로 (중간에 목소리가 바뀌지 않게). 도중에 막히면 처음부터 다음 도구로.
        for name, fn in ENGINES:
            if name in dead:
                continue
            try:
                for k, text in enumerate(data["steps"]):
                    try:
                        clip = fn(text, g)
                    except Quota:
                        raise
                    except Exception as e:  # 일시 오류는 한 번 더
                        print(f"[음성] {name} {g}{k} 다시 시도: {e}")
                        clip = fn(text, g)
                    (out / f"{g}{k}.mp3").write_bytes(clip)
                used[g] = name
                break
            except Quota as e:
                print(f"[음성] {name} 사용 불가(한도·키) → 다음 도구로: {e}")
                dead.add(name)
            except Exception as e:
                print(f"[음성] {name} {g} 실패 → 다음 도구로: {e}")
            for f in out.glob(f"{g}*.mp3"):
                f.unlink()
        else:
            print(f"[음성] {g} 목소리를 만들지 못해 비워 둠 (화면은 기기 목소리로 읽음)")
    meta = {"date": data["date"], "n": len(data["steps"]), "voices": used}
    (out / "brief.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"[음성] 완료: {meta}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
