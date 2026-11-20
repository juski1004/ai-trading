"""AI 대결 화면 BGM '개장' — 경제뉴스 오프닝 느낌 (똑딱이는 신스 박자 + 긴장감 있는 화음). 직접 작곡·합성.
실행: python web/app/bgm/news.py web/app/bgm/battle.mp3
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from compose import SR, env, hz  # noqa: E402

BPM = 116
BEAT = 60 / BPM
S16 = BEAT / 4


def saw(f, dur, cutoff=0.5, a=0.003, d=0.12, s=0.3, r=0.04, det=0.004):  # 부드러운 톱니 신스 (배음 수 제한)
    n = int(dur * SR); t = np.arange(n) / SR; v = np.zeros(n)
    kmax = max(1, int(cutoff * 9000 / f))
    for dd in (-det, det):
        for k in range(1, min(kmax, 24) + 1):
            v += np.sin(2 * np.pi * f * (1 + dd) * k * t) / k * (0.85 ** k)
    return v / 2 * env(n, a=a, d=d, s=s, r=r)


def pluck(f, dur):  # 똑딱이는 16분 신스
    n = int(dur * SR); t = np.arange(n) / SR
    v = np.sin(2 * np.pi * f * t + 1.8 * np.exp(-30 * t) * np.sin(2 * np.pi * f * 2 * t))
    return v * np.exp(-14 * t) * env(n, a=0.002, d=0.05, s=1, r=0.02)


def pad(f, dur):
    return saw(f, dur, cutoff=0.25, a=0.4, d=0.4, s=0.8, r=0.3, det=0.006)


def kick():
    n = int(0.3 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * (45 + 110 * np.exp(-35 * t)) * t) * np.exp(-10 * t)


def clap(rng):
    n = int(0.2 * SR); t = np.arange(n) / SR; x = rng.standard_normal(n)
    x = x - np.convolve(x, np.ones(4) / 4, "same")
    e = sum(np.exp(-60 * np.clip(t - o, 0, None)) * (t >= o) for o in (0, 0.012, 0.024)) + np.exp(-12 * t) * 0.5
    return x * e * 0.6


def tick():  # 시계 초침 같은 짧은 '틱'
    n = int(0.02 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * 3200 * t) * np.exp(-300 * t)


def stab(names, dur):  # 금관 같은 화음 찌르기
    return sum(saw(hz(nm), dur, cutoff=0.7, a=0.005, d=0.15, s=0.2, r=0.05) for nm in names) / len(names)


# 단조지만 앞으로 나아가는 진행: Am - F - C - G / Am - F - Dm - E
CH = [["A3", "C4", "E4"], ["F3", "A3", "C4"], ["C4", "E4", "G4"], ["G3", "B3", "D4"],
      ["A3", "C4", "E4"], ["F3", "A3", "C4"], ["D3", "F3", "A3"], ["E3", "G#3", "B3"]]
ROOT = ["A1", "F1", "C2", "G1", "A1", "F1", "D2", "E1"]
ARP = [0, 2, 1, 2, 0, 2, 1, 2, 0, 2, 1, 2, 0, 1, 2, 1]
MEL = [[("E5", 1.5), ("D5", .5), ("C5", 1), ("E5", 1)], [("F5", 3), ("C5", 1)], [("G5", 1.5), ("E5", .5), ("C5", 2)],
       [("D5", 2), ("B4", 2)], [("A5", 1.5), ("G5", .5), ("E5", 1), ("C5", 1)], [("F5", 2), ("A5", 2)],
       [("F5", 1), ("E5", 1), ("D5", 1), ("A4", 1)], [("B4", 2), ("G#4", 2)]]


def render(passes=3):
    rng = np.random.default_rng(3)
    bar = 4 * BEAT; L = int(len(CH) * bar * passes * SR); mix = np.zeros((L + SR, 2))

    def put(x, s, g, pan=0.0):
        i = int(s * SR); x = x[: max(0, L + SR - i)]
        mix[i:i + len(x), 0] += x * g * (1 - pan) ** .5; mix[i:i + len(x), 1] += x * g * (1 + pan) ** .5

    for p in range(passes):
        for b, ch in enumerate(CH):
            t0 = (p * len(CH) + b) * bar
            for k, nm in enumerate(ch):  # 바탕 화음
                put(pad(hz(nm), bar), t0, 0.06, pan=-0.3 + 0.3 * k)
            for i in range(16):  # 16분 똑딱 신스 (위아래 옥타브 번갈아)
                nm = ch[ARP[i]]; f = hz(nm) * (2 if i % 8 < 4 else 4)
                put(pluck(f, S16 * 0.9), t0 + i * S16, 0.07 if i % 4 else 0.1, pan=(0.35 if i % 2 else -0.35))
            r = hz(ROOT[b])  # 베이스: 8분으로 계속 밀어줌
            for i in range(8):
                put(saw(r * (2 if i % 2 else 1), BEAT / 2 * 0.85, cutoff=0.35, a=0.003, d=0.08, s=0.5, r=0.03), t0 + i * BEAT / 2, 0.16)
            for i in range(16):
                put(tick(), t0 + i * S16, 0.05 if i % 4 else 0.09, pan=0.5)
            if p == 0 and b < 4:
                continue  # 처음 네 마디는 드럼 없이 쌓아 올리기
            for bt in range(4):
                put(kick(), t0 + bt * BEAT, 0.5)
            for bt in (1, 3):
                put(clap(rng), t0 + bt * BEAT, 0.18)
            if b % 2 == 1:
                put(stab(ch, BEAT * 0.5), t0 + 3.5 * BEAT, 0.12)
            if p >= 1:  # 2회차부터 주제 선율
                t = t0
                for nm, d in MEL[b]:
                    put(saw(hz(nm), d * BEAT * 0.95, cutoff=0.6, a=0.02, d=0.2, s=0.6, r=0.08), t, 0.11, pan=0.05)
                    t += d * BEAT
    out = mix[:L]
    wet = out.copy()
    for dly in (BEAT * 0.75, BEAT * 1.5):  # 박자에 맞춘 메아리
        n = int(dly * SR); g = 0.18 if dly < BEAT else 0.09
        wet[n:, 0] += out[:-n, 1] * g; wet[n:, 1] += out[:-n, 0] * g
    return wet / np.max(np.abs(wet)) * 0.82


if __name__ == "__main__":
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else "battle.mp3")
    a = (render() * 32767).astype(np.int16); wav = dst.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(dst)], check=True)
    wav.unlink(); print(dst, f"{len(a) / SR:.1f}초")
