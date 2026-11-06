"""잔잔한 배경음 (2026-10-25 사용자 요청: 더 잔잔하게, 소리 작게). 드럼 없음. 직접 작곡·합성.
  - 메인 '저녁 정리' : 느린 전자 피아노 화음 + 부드러운 바탕음, 가끔 짧은 선율
  - 대결 '조용한 승부': 같은 악기 + 아주 작은 맥박(8분 음표)만 더해 살짝 긴장감
실행: python web/app/bgm/calm.py web/app/bgm/main.mp3 main
      python web/app/bgm/calm.py web/app/bgm/battle.mp3 battle
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from compose import SR, env, hz  # noqa: E402

BPM = 64
BEAT = 60 / BPM


def epiano(f, dur, vel=1.0):  # 부드러운 전자 피아노 (금속성 타건을 약하게)
    n = int(dur * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * t + 0.8 * np.exp(-3 * t) * np.sin(2 * np.pi * f * t))
    tine = np.sin(2 * np.pi * f * t + 1.2 * np.exp(-16 * t) * np.sin(2 * np.pi * f * 14 * t)) * np.exp(-8 * t)
    trem = 1 + 0.06 * np.sin(2 * np.pi * 3.5 * t)
    return (body * 0.85 + tine * 0.15) * trem * env(n, a=0.01, d=1.4, s=0.4, r=0.6) * vel


def pad(f, dur):  # 천천히 차오르는 바탕음 (사인 두 개를 살짝 어긋나게)
    n = int(dur * SR); t = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * 0.998 * t) + np.sin(2 * np.pi * f * 1.002 * t) + 0.3 * np.sin(4 * np.pi * f * t)
    return v / 2.3 * env(n, a=min(1.2, dur * 0.4), d=0.5, s=0.85, r=min(1.0, dur * 0.3))


def pulse(f, dur):  # 대결 화면용 아주 작은 맥박
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t) * np.exp(-9 * t) * env(n, a=0.005, d=0.05, s=1, r=0.03)


# Dmaj9 - Bm9 - Gmaj7 - Aadd9 / F#m7 - Bm7 - Em9 - A7sus (밝고 편안한 순환)
CH = [["D3", "F#3", "A3", "C#4", "E4"], ["B2", "D3", "F#3", "A3", "C#4"], ["G2", "B2", "D3", "F#3"], ["A2", "C#3", "E3", "B3"],
      ["F#2", "A2", "C#3", "E3"], ["B2", "D3", "F#3", "A3"], ["E2", "G2", "B2", "D3", "F#3"], ["A2", "D3", "E3", "G3"]]
ROOT = ["D2", "B1", "G1", "A1", "F#1", "B1", "E2", "A1"]
MEL = [[("A4", 2), ("F#4", 2)], [("R", 4)], [("D5", 1.5), ("B4", .5), ("A4", 2)], [("R", 4)],
       [("C#5", 2), ("A4", 2)], [("R", 4)], [("B4", 1.5), ("G4", .5), ("F#4", 2)], [("E4", 3), ("R", 1)]]


def render(kind="main", passes=3):
    rng = np.random.default_rng(11)
    bar = 4 * BEAT; L = int(len(CH) * bar * passes * SR); mix = np.zeros((L + 2 * SR, 2))

    def put(x, s, g, pan=0.0):
        i = int(s * SR); x = x[: max(0, len(mix) - i)]
        mix[i:i + len(x), 0] += x * g * (1 - pan) ** .5; mix[i:i + len(x), 1] += x * g * (1 + pan) ** .5

    for p in range(passes):
        for b, ch in enumerate(CH):
            t0 = (p * len(CH) + b) * bar
            for k, nm in enumerate(ch):  # 화음을 아래에서 위로 천천히 펼침
                put(epiano(hz(nm), 3.6 * BEAT, 0.8), t0 + 0.06 * k + rng.uniform(0, 0.01), 0.09, pan=-0.25 + 0.12 * k)
            if b % 2:
                for k, nm in enumerate(ch[1:4]):  # 3박에 가볍게 한 번 더
                    put(epiano(hz(nm) * 2, 1.6 * BEAT, 0.45), t0 + 2.5 * BEAT + 0.05 * k, 0.05, pan=0.2)
            for nm in ch[:3]:
                put(pad(hz(nm), bar * 1.05), t0, 0.035)
            put(pad(hz(ROOT[b]), bar * 1.02), t0, 0.12)
            if kind == "battle" and not (p == 0 and b < 2):
                for i in range(8):  # 8분 맥박: 근음과 5도를 번갈아
                    f = hz(ROOT[b]) * (4 if i % 2 == 0 else 6)
                    put(pulse(f, BEAT * 0.45), t0 + i * BEAT / 2, 0.05 if i % 2 else 0.07, pan=(0.3 if i % 2 else -0.3))
            if p >= 1:
                t = t0
                for nm, d in MEL[b]:
                    if nm != "R":
                        put(epiano(hz(nm), d * BEAT * 1.3, 0.9), t, 0.08, pan=0.1)
                    t += d * BEAT
    out = mix[:L]
    k = np.ones(6) / 6  # 고음을 깎아 귀에 편하게
    out = np.stack([np.convolve(out[:, c], k, "same") for c in (0, 1)], 1)
    wet = out.copy()
    for dly, g in ((0.051, .32), (0.083, .26), (0.127, .2), (0.191, .14), (0.29, .09)):
        n = int(dly * SR); wet[n:, 0] += out[:-n, 1] * g; wet[n:, 1] += out[:-n, 0] * g
    fade = int(1.5 * SR)  # 반복 이음새가 튀지 않게 앞뒤 살짝
    ramp = np.linspace(0, 1, fade)[:, None]
    wet[:fade] *= ramp; wet[-fade:] *= ramp[::-1]
    return wet / np.max(np.abs(wet)) * 0.6  # 최종 크기는 인코딩 때 -24 LUFS로 맞춤 (이전 곡 -18 보다 작게)


if __name__ == "__main__":
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else "main.mp3")
    kind = sys.argv[2] if len(sys.argv) > 2 else "main"
    a = (render(kind) * 32767).astype(np.int16); wav = dst.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", "loudnorm=I=-24:TP=-3:LRA=11", "-ar", str(SR), "-b:a", "112k", str(dst)], check=True)
    wav.unlink(); print(dst, f"{len(a) / SR:.1f}초")
