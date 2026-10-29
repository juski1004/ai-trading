"""구글 TTS 음성 만들기 (깡통 내레이션: 2026-10-28 사용자 선택 gemini:Charon)
- 문장에 ' || ' 가 있으면 줄별로 01.wav, 02.wav … (줄 사이 21초 쉬고, 한도 초과(429)면 65초 뒤 최대 3번 다시)
- 이름이 gemini:<목소리> 이면 Gemini API(GEMINI_API_KEY, AI Studio와 같은 목소리), 아니면 구글 클라우드 TTS(GOOGLE_TTS_API_KEY)
실행: python tools/tts_samples.py <출력폴더> "<문장>" gemini:Charon,ko-KR-Wavenet-C,...
"""
import base64, json, os, sys, urllib.error, urllib.request, wave
from pathlib import Path

out, text, voices = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
LINES = [t.strip() for t in text.split("||") if t.strip()]
out.mkdir(parents=True, exist_ok=True); res = {}
STYLE = os.getenv("TTS_STYLE", "")
SPEED = float(os.getenv("TTS_SPEED") or 1)  # 1.2 = 1.2배 빠르게 (음높이 그대로, ffmpeg atempo)


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode()[:300]}")


import time
from array import array

GROUP = int(os.getenv("TTS_GROUP") or 1)  # 2 이상이면 그 줄 수만큼 한 번에 요청하고 쉬는 곳에서 줄별로 자름 (무료 하루 한도 아끼기)
MODELS = [os.getenv("TTS_MODEL", "gemini-2.5-flash-preview-tts"), "gemini-2.5-pro-preview-tts"]


def split_pcm(pcm: bytes, n: int) -> list[bytes]:
    """24kHz 16bit 소리를 가장 긴 무음 n-1곳에서 잘라 n개로."""
    a = array("h"); a.frombytes(pcm); fr = 480  # 20ms
    rms = [(sum(x * x for x in a[i:i + fr]) / fr) ** 0.5 for i in range(0, len(a) - fr, fr)]
    th = max(rms) * 0.04; runs = []; st = None
    for i, v in enumerate(rms + [th * 10]):
        if v < th and st is None: st = i
        elif v >= th and st is not None:
            if st > 0 and i < len(rms): runs.append((i - st, st, i))
            st = None
    cuts = sorted((s0 + e0) // 2 * fr for _, s0, e0 in sorted(runs, reverse=True)[: n - 1])
    if len(cuts) < n - 1: raise RuntimeError(f"쉬는 곳이 {len(cuts)}곳뿐이라 {n}줄로 못 자름")
    edges = [0] + cuts + [len(a)]
    return [a[edges[i]:edges[i + 1]].tobytes() for i in range(n)]


def save(pcm: bytes, dst):
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    if abs(SPEED - 1) > 0.01:
        import subprocess
        tmp = dst.with_suffix(".tmp.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(dst), "-filter:a", f"atempo={SPEED}", str(tmp)], check=True)
        tmp.replace(dst)


def gemini_pcm(name, line):
    last = None
    for model in MODELS:
        try:
            return _gemini_pcm(name, line, model)
        except RuntimeError as e:
            last = e
            if not str(e).startswith("429"): raise
    raise last


def _gemini_pcm(name, line, model):
    for k in range(4):
        try:
            j = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={os.environ['GEMINI_API_KEY']}",
                     {"contents": [{"parts": [{"text": (STYLE + ": " if STYLE else "") + line}]}],
                      "generationConfig": {"responseModalities": ["AUDIO"],
                                           "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": name}}}}})
            break
        except RuntimeError as e:
            if not str(e).startswith("429") or k == 2: raise
            time.sleep(65)
    return base64.b64decode(j["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])


def gemini(name, line, dst):
    save(gemini_pcm(name, line), dst)


for v in voices:
    try:
        if v.startswith("gemini:"):
            name = v.split(":", 1)[1]
            if len(LINES) > 1 and GROUP > 1:
                d = out / name; d.mkdir(exist_ok=True)
                for g0 in range(0, len(LINES), GROUP):
                    part = LINES[g0:g0 + GROUP]
                    if g0: time.sleep(21)
                    text_g = "\n".join(part) if len(part) > 1 else part[0]
                    pcm = gemini_pcm(name, ("각 줄 끝마다 1초씩 확실히 쉬고 읽어. " if len(part) > 1 else "") + text_g)
                    for i, chunk in enumerate(split_pcm(pcm, len(part)) if len(part) > 1 else [pcm], g0 + 1):
                        save(chunk, d / f"{i:02d}.wav")
            elif len(LINES) > 1:
                d = out / name; d.mkdir(exist_ok=True)
                for i, line in enumerate(LINES, 1):
                    if i > 1: time.sleep(21)
                    gemini(name, line, d / f"{i:02d}.wav")
            else:
                gemini(name, text, out / f"{name}.wav")
        else:
            j = post(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={os.environ['GOOGLE_TTS_API_KEY']}",
                     {"input": {"text": text}, "voice": {"languageCode": "ko-KR", "name": v}, "audioConfig": {"audioEncoding": "MP3"}})
            (out / f"{v}.mp3").write_bytes(base64.b64decode(j["audioContent"]))
        res[v] = "ok"
    except Exception as e:
        res[v] = f"실패: {str(e)[:300]}"
    print(v, res[v])
(out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
