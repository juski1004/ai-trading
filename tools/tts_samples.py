"""구글 TTS 목소리 비교 샘플 (깡통 내레이션 목소리 고르기용, 수동 실행)
- 이름이 gemini:<목소리> 이면 Gemini API(GEMINI_API_KEY, AI Studio와 같은 목소리), 아니면 구글 클라우드 TTS(GOOGLE_TTS_API_KEY)
실행: python tools/tts_samples.py <출력폴더> "<문장>" gemini:Charon,ko-KR-Wavenet-C,...
"""
import base64, json, os, sys, urllib.error, urllib.request, wave
from pathlib import Path

out, text, voices = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
out.mkdir(parents=True, exist_ok=True); res = {}
STYLE = os.getenv("TTS_STYLE", "")


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode()[:300]}")


for v in voices:
    try:
        if v.startswith("gemini:"):
            name = v.split(":", 1)[1]
            j = post(f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('TTS_MODEL', 'gemini-2.5-flash-preview-tts')}:generateContent?key={os.environ['GEMINI_API_KEY']}",
                     {"contents": [{"parts": [{"text": (STYLE + ": " if STYLE else "") + text}]}],
                      "generationConfig": {"responseModalities": ["AUDIO"],
                                           "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": name}}}}})
            pcm = base64.b64decode(j["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            with wave.open(str(out / f"{name}.wav"), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
        else:
            j = post(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={os.environ['GOOGLE_TTS_API_KEY']}",
                     {"input": {"text": text}, "voice": {"languageCode": "ko-KR", "name": v}, "audioConfig": {"audioEncoding": "MP3"}})
            (out / f"{v}.mp3").write_bytes(base64.b64decode(j["audioContent"]))
        res[v] = "ok"
    except Exception as e:
        res[v] = f"실패: {str(e)[:300]}"
    print(v, res[v])
(out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
