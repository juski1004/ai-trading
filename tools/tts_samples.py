"""구글 클라우드 TTS 목소리 비교 샘플 (깡통 내레이션 목소리 고르기용, 수동 실행)
실행: GOOGLE_TTS_API_KEY=... python tools/tts_samples.py <출력폴더> "<문장>" voice1,voice2,...
"""
import base64, json, sys, urllib.request
from pathlib import Path
import os

out, text, voices = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
out.mkdir(parents=True, exist_ok=True); key = os.environ["GOOGLE_TTS_API_KEY"]; res = {}
for v in voices:
    body = {"input": {"text": text}, "voice": {"languageCode": "ko-KR", "name": v},
            "audioConfig": {"audioEncoding": "MP3", "sampleRateHertz": 24000}}
    req = urllib.request.Request(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        a = json.load(urllib.request.urlopen(req, timeout=60))["audioContent"]
        (out / f"{v}.mp3").write_bytes(base64.b64decode(a)); res[v] = "ok"
    except Exception as e:
        res[v] = f"실패: {getattr(e, 'code', '')} {str(e)[:120]}"
    print(v, res[v])
(out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
