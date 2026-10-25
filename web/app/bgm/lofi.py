"""메인 화면 BGM '장 마감 카페' — 로파이 재즈 (전자 피아노 + 잔잔한 드럼). 직접 작곡·합성.
실행: python web/app/bgm/lofi.py web/app/bgm/main.mp3
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from compose import SR, env, hz  # noqa: E402

BPM = 78
BEAT = 60 / BPM
SW = 0.62  # 16분음표 스윙 (0.5 = 정박)
rng = np.random.default_rng(7)


def epiano(f, dur, vel=1.0):  # FM 전자 피아노 (로즈 느낌: 몸통 + 금속성 타건)
    n = int(dur * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * t + 1.2 * np.exp(-2.5 * t) * np.sin(2 * np.pi * f * t))
    tine = np.sin(2 * np.pi * f * t + 2.0 * np.exp(-14 * t) * np.sin(2 * np.pi * f * 14 * t)) * np.exp(-6 * t)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)
    return (body * 0.8 + tine * 0.35 * vel) * trem * env(n, a=0.004, d=0.9, s=0.45, r=0.25) * vel


def sub(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * env(n, a=0.01, d=0.3, s=0.7, r=0.08)


def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * (48 + 70 * np.exp(-30 * t)) * t) * np.exp(-9 * t)


def snare():
    n = int(0.25 * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = np.convolve(noise, np.ones(6) / 6, "same")  # 거친 고음 깎기 (부드러운 브러시 느낌)
    return (noise * np.exp(-16 * t) * 0.7 + np.sin(2 * np.pi * 190 * t) * np.exp(-25 * t) * 0.4)


def hat(open_=False):
    n = int((0.12 if open_ else 0.05) * SR); t = np.arange(n) / SR
    x = rng.standard_normal(n); x = x - np.convolve(x, np.ones(3) / 3, "same")
    return x * np.exp(-(18 if open_ else 60) * t)


# 화성: Fmaj9 - Em7 - Dm9 - Cmaj7 / Bbmaj7 - Am7 - Gm7 - C7sus  (밝고 차분한 순환)
CH = [["F3", "A3", "C4", "E4", "G4"], ["E3", "G3", "B3", "D4"], ["D3", "F3", "A3", "C4", "E4"], ["C3", "E3", "G3", "B3"],
      ["A#2", "D3", "F3", "A3"], ["A2", "C3", "E3", "G3"], ["G2", "A#2", "D3", "F3", "A3"], ["C3", "F3", "G3", "A#3"]]
ROOT = ["F1", "E1", "D1", "C2", "A#1", "A1", "G1", "C2"]
# 오른손 짧은 멜로디 (2회차에만, 질리지 않게)
MEL = [[("C5", 1.5), ("A4", .5), ("G4", 2)], [("B4", 1), ("D5", 1), ("E5", 2)], [("F5", 1.5), ("E5", .5), ("C5", 2)],
       [("B4", 3), ("R", 1)], [("D5", 1), ("F5", 1), ("A5", 1.5), ("G5", .5)], [("E5", 2), ("C5", 2)],
       [("D5", 1), ("A#4", 1), ("A4", 1), ("F4", 1)], [("G4", 3), ("R", 1)]]


def render(passes=3):
    bar = 4 * BEAT; L = int(len(CH) * bar * passes * SR); mix = np.zeros((L + SR, 2))

    def put(x, s, g, pan=0.0):
        i = int(s * SR); x = x[: max(0, L + SR - i)]
        mix[i:i + len(x), 0] += x * g * (1 - pan) ** .5; mix[i:i + len(x), 1] += x * g * (1 + pan) ** .5

    def at(b16):  # 16분 위치 → 초 (스윙)
        beat, k = divmod(b16, 4); pair, odd = divmod(k, 2)
        return (beat + pair * 0.5 + (SW * 0.5 if odd else 0)) * BEAT

    for p in range(passes):
        for b, ch in enumerate(CH):
            t0 = (p * len(CH) + b) * bar
            # 피아노: 1박에 화음, 2.5박에 다시 살짝 (당김)
            for k, nm in enumerate(ch):
                put(epiano(hz(nm), 2.3 * BEAT, 0.9), t0 + 0.012 * k, 0.10, pan=-0.2 + 0.1 * k)
                put(epiano(hz(nm), 1.4 * BEAT, 0.6), t0 + at(10) + 0.01 * k, 0.07, pan=-0.2 + 0.1 * k)
            r = hz(ROOT[b])
            put(sub(r, 1.8 * BEAT), t0, 0.33); put(sub(r * 1.5 if b % 2 else r, 0.9 * BEAT), t0 + at(10), 0.26)
            if p == 0 and b < 2:
                continue  # 시작 두 마디는 피아노·베이스만
            for s16 in (0, 7, 10):
                put(kick(), t0 + at(s16), 0.45 if s16 == 0 else 0.3)
            for s16 in (4, 12):
                put(snare(), t0 + at(s16), 0.22)
            for s16 in range(0, 16, 2):
                put(hat(open_=(s16 == 14)), t0 + at(s16), 0.05 if s16 % 4 else 0.07, pan=0.3)
            if p >= 1:
                t = t0
                for nm, d in MEL[b]:
                    if nm != "R":
                        put(epiano(hz(nm), d * BEAT * 1.1, 1.0), t, 0.14, pan=0.15)
                    t += d * BEAT
    out = mix[:L]
    # 따뜻하게: 고음 살짝 깎기 (레코드판 잡음은 거슬린다고 해서 뺌)
    k = np.ones(4) / 4
    out = np.stack([np.convolve(out[:, c], k, "same") for c in (0, 1)], 1)
    wet = out.copy()
    for dly, g in ((0.043, .3), (0.067, .24), (0.097, .18), (0.149, .12)):
        n = int(dly * SR); wet[n:, 0] += out[:-n, 1] * g; wet[n:, 1] += out[:-n, 0] * g
    return wet / np.max(np.abs(wet)) * 0.8


if __name__ == "__main__":
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else "main.mp3")
    a = (render() * 32767).astype(np.int16); wav = dst.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(dst)], check=True)
    wav.unlink(); print(dst, f"{len(a) / SR:.1f}초")
