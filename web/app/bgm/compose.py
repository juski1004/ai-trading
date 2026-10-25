"""메인 화면 BGM '출항' — 90년대 PC 전략 게임(FM 음원) 느낌의 새로 만든 곡.

멜로디·화성 모두 직접 쓴 곡이라 저작권 걱정 없음. numpy로 합성 → WAV → ffmpeg로 MP3.
실행: python web/app/bgm/compose.py web/app/bgm/main.mp3
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 100
BEAT = 60 / BPM
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    n, o = name[:-1], int(name[-1])
    return 440 * 2 ** ((NOTE[n] + 12 * (o + 1) - 69) / 12)


def env(n, a=0.01, d=0.15, s=0.6, r=0.12):
    t = np.arange(n) / SR; L = n / SR
    e = np.where(t < a, t / a, np.where(t < a + d, 1 - (1 - s) * (t - a) / d, s))
    rel = np.clip((L - t) / r, 0, 1)
    return e * rel


def fm(f, dur, ratio=1.0, index=2.0, idx_decay=3.0, **kw):
    n = int(dur * SR); t = np.arange(n) / SR
    I = index * np.exp(-idx_decay * t)
    return np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t)) * env(n, **kw)


def brass(f, dur):   # FM 금관 (두 연산자, 약간 늦게 열림)
    n = int(dur * SR); t = np.arange(n) / SR
    I = 2.6 * (1 - np.exp(-18 * t)) * np.exp(-0.8 * t) + 0.6
    v = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * t))
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t - 0.25, 0, 1)
    v = np.sin(2 * np.pi * f * np.cumsum(vib) / SR + I * np.sin(2 * np.pi * f * t))
    return v * env(n, a=0.04, d=0.2, s=0.75, r=0.1)


def flute(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t * 3 - 0.6, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    v = np.sin(ph + 0.35 * np.sin(2 * ph)) + 0.15 * np.sin(2 * ph)
    return v * env(n, a=0.05, d=0.1, s=0.85, r=0.08)


def harpsi(f, dur):  # 하프시코드 느낌 (높은 비율 FM + 빠른 감쇠)
    return fm(f, dur, ratio=3.0, index=3.0, idx_decay=8, a=0.002, d=0.25, s=0.15, r=0.05) * 0.9


def bass(f, dur):
    return fm(f, dur, ratio=1.0, index=1.6, idx_decay=4, a=0.005, d=0.2, s=0.55, r=0.05)


def strings(f, dur):  # 현악 패드 (살짝 어긋난 세 줄)
    n = int(dur * SR); t = np.arange(n) / SR
    v = sum(np.sin(2 * np.pi * f * (1 + d) * t + 0.8 * np.sin(2 * np.pi * f * 2 * t)) for d in (-0.003, 0, 0.003)) / 3
    return v * env(n, a=0.25, d=0.3, s=0.8, r=0.3)


def timp(dur, f=73.4):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(1)
    return (np.sin(2 * np.pi * f * t * (1 + 0.15 * np.exp(-20 * t))) * np.exp(-5 * t)
            + 0.3 * rng.standard_normal(n) * np.exp(-30 * t))


# 화성 (한 마디 = 4박)
CH = {"D": ["D3", "F#3", "A3"], "A/C#": ["C#3", "E3", "A3"], "Bm": ["B2", "D3", "F#3"], "G": ["G2", "B2", "D3"],
      "A": ["A2", "C#3", "E3"], "F#m": ["F#2", "A2", "C#3"], "Em": ["E2", "G2", "B2"]}
ROOT = {"D": "D2", "A/C#": "C#2", "Bm": "B1", "G": "G1", "A": "A1", "F#m": "F#2", "Em": "E2"}
PROG = ["D", "A/C#", "Bm", "G", "D", "G", "A", "A",
        "G", "A", "F#m", "Bm", "Em", "A", "D", "D"]
MEL = [  # (음, 박)  — 새로 쓴 '출항' 주제
    [("D5", 1.5), ("A4", .5), ("F#4", 1), ("A4", 1)], [("E5", 1.5), ("D5", .5), ("C#5", 1), ("A4", 1)],
    [("D5", 1), ("F#5", 1), ("E5", 1), ("D5", 1)], [("B4", 3), ("A4", 1)],
    [("F#5", 1.5), ("E5", .5), ("D5", 1), ("A4", 1)], [("B4", 1), ("D5", 1), ("G5", 1), ("F#5", 1)],
    [("E5", 1), ("D5", .5), ("C#5", .5), ("B4", 1), ("C#5", 1)], [("A4", 3), ("R", 1)],
    [("B4", 1), ("D5", 1), ("G5", 2)], [("A5", 1.5), ("G5", .5), ("F#5", 1), ("E5", 1)],
    [("F#5", 1), ("C#5", 1), ("A4", 1), ("C#5", 1)], [("D5", 3), ("F#5", 1)],
    [("G5", 1.5), ("F#5", .5), ("E5", 1), ("B4", 1)], [("C#5", 1), ("E5", 1), ("A5", 1), ("G5", 1)],
    [("F#5", 2), ("E5", 1), ("D5", 1)], [("D5", 3), ("R", 1)],
]


def render(passes=2) -> np.ndarray:
    bar = 4 * BEAT; total = int(len(PROG) * bar * passes * SR) + SR
    mix = np.zeros((total, 2))

    def put(x, start, gain, pan=0.0):
        i = int(start * SR); x = x[: max(0, total - i)]
        mix[i:i + len(x), 0] += x * gain * (1 - pan) ** .5
        mix[i:i + len(x), 1] += x * gain * (1 + pan) ** .5

    for p in range(passes):
        for b, ch in enumerate(PROG):
            t0 = (p * len(PROG) + b) * bar
            for k, nme in enumerate(CH[ch]):  # 현악 패드
                put(strings(hz(nme) * 2, bar), t0, 0.07, pan=-0.4 + 0.4 * k)
            r = hz(ROOT[ch])  # 베이스: 1·2.5·3박
            for at, d in ((0, 1.4), (1.5, .45), (2, 1.9)):
                put(bass(r, d * BEAT), t0 + at * BEAT, 0.28)
            notes = CH[ch] + [CH[ch][0][:-1] + str(int(CH[ch][0][-1]) + 1)]
            steps = 8 if p == 0 else 16  # 하프시코드 아르페지오 (2회차는 16분으로 더 촘촘)
            seq = [0, 1, 2, 3, 2, 1, 2, 3] * 2
            for i in range(steps):
                nm = notes[seq[i] % 4]
                put(harpsi(hz(nm) * 4, bar / steps * 0.95), t0 + i * bar / steps, 0.07 if p == 0 else 0.055, pan=0.35)
            if b % 4 == 0 or b in (7, 15):  # 팀파니
                put(timp(1.2, hz(ROOT[ch]) * 2), t0, 0.25)
            if b in (7, 15):
                for k in range(4):
                    put(timp(.4, hz("A1") * 2), t0 + (3 + k * .25) * BEAT, 0.12 + 0.03 * k)
            # 주선율: 1회차 플루트+금관 옥타브 아래, 2회차 금관이 앞으로
            t = t0
            for nm, d in MEL[b]:
                if nm != "R":
                    f = hz(nm)
                    put(flute(f, d * BEAT * 0.97), t, 0.20 if p == 0 else 0.13, pan=-0.15)
                    put(brass(f / 2 if p == 0 else f, d * BEAT * 0.95), t, 0.10 if p == 0 else 0.17, pan=0.1)
                t += d * BEAT
            if b % 2 == 1:  # 금관 화음 찌르기 (마디 끝)
                for nme in CH[ch]:
                    put(brass(hz(nme) * 2, BEAT * .45), t0 + 3.5 * BEAT, 0.035)
    # 간단한 잔향 (지연 합)
    out = mix.copy()
    for dly, g in ((0.031, .35), (0.047, .28), (0.073, .22), (0.113, .16), (0.171, .1)):
        k = int(dly * SR); out[k:, 0] += mix[:-k, 1] * g; out[k:, 1] += mix[:-k, 0] * g
    out = out[: int(len(PROG) * bar * passes * SR)]  # 정확히 마디 끝에서 잘라 반복 재생 이음새 없앰
    return out / np.max(np.abs(out)) * 0.85


if __name__ == "__main__":
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else "main.mp3")
    a = (render() * 32767).astype(np.int16)
    wav = dst.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(dst)], check=True)
    wav.unlink()
    print(dst, f"{len(a) / SR:.1f}초")
