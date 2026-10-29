"""깡통 내레이션 무료 음성 (Qwen3-TTS 목소리 복제, CPU). 2026-10-29 사용자가 고른 ★2 Fenrir 샘플을 복제.
구글 Gemini 무료 한도가 하루 몇 번뿐이라, 한도 없는 이 방식을 기본 대체로 씀 (일레븐랩스 크레딧이 없을 때).
실행: python tools/qwen_tts_run.py <출력폴더> "<줄1 || 줄2 || …>" [기준음성.wav] [기준음성 문장.txt]
결과: <출력폴더>/01.wav, 02.wav … , result.json
"""
import json, sys, time
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
lines = [t.strip() for t in sys.argv[2].split("||") if t.strip()]
ref = sys.argv[3] if len(sys.argv) > 3 else "tools/voices/kkt_ref.wav"
ref_text = Path(sys.argv[4] if len(sys.argv) > 4 else "tools/voices/kkt_ref.txt").read_text(encoding="utf-8").strip()
torch.set_num_threads(max(1, torch.get_num_threads()))
m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-0.6B-Base", device_map="cpu", dtype=torch.float32)
p = m.create_voice_clone_prompt(ref_audio=ref, ref_text=ref_text, x_vector_only_mode=False)
res = {}
for i, line in enumerate(lines, 1):
    t = time.time()
    try:
        w, sr = m.generate_voice_clone(text=line, language="Korean", voice_clone_prompt=p)
        sf.write(out / f"{i:02d}.wav", w[0], sr); res[f"{i:02d}"] = round(len(w[0]) / sr, 2)
    except Exception as e:
        res[f"{i:02d}"] = f"실패: {type(e).__name__}: {str(e)[:120]}"
    print(i, res[f"{i:02d}"], f"{time.time() - t:.0f}s", flush=True)
(out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
