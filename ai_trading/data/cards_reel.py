"""장마감 모션 릴스 (1080x1920, 약 20초, 배경음).
2026-10-30 사용자: "카드 넘기는 것만으로는 카드뉴스와 차이가 없어 밋밋해. 모션그래픽, 확대·축소, 글씨 날아오기"
→ 카드 이미지를 넘기지 않고, 같은 날 데이터(cards.json 의 reel)로 장면마다 직접 움직이는 화면을 그린다.

장면: ① 표지(진행자 사진 줌아웃 + 큰 글씨 날아오기) ② 지수(숫자 올라가기 + 상승·하락 막대)
      ③ 많이 오른 3종목 ④ 많이 내린 3종목(줄마다 날아오기) ⑤ 수급 막대 ⑥ 댓글 '연구소' 안내
장면 사이는 확대되며 넘어가는 전환. 맨 위에 장면 진행 막대.
결과: <web>/data/cards/reel.mp4, reel_cover.jpg
실행: python -m ai_trading.data.cards_reel web
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ai_trading.data.cards import TEAM_IMG, _font as F

W, H, FPS = 1080, 1920, 30
# 2026-10-30 사용자: "밝은 화면으로" → 미색 바탕 + 진한 글씨 + 흰 패널
BG1, BG2 = (250, 249, 245), (236, 240, 248)
WHITE, FG, DIM, YEL = (255, 255, 255), (20, 22, 30), (112, 116, 128), (255, 214, 10)
RED, BLUE, ACC = (226, 52, 92), (40, 98, 222), (38, 99, 235)
SCENES = [3.6, 3.6, 3.4, 3.4, 3.0, 3.4]  # 초
TR = 0.35  # 전환 길이


# ---------- 움직임 ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, d): return clamp((t - a) / d)
def out3(x): return 1 - (1 - x) ** 3
def back(x, s=1.7): x -= 1; return 1 + (s + 1) * x ** 3 + s * x ** 2


@lru_cache(maxsize=512)
def sprite(text: str, weight: str, size: int, color: tuple) -> Image.Image:
    f = F(weight, size); d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    im = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=f, fill=color + (255,))
    return im


def put(base: Image.Image, sp: Image.Image, x: float, y: float, scale=1.0, alpha=1.0, anchor="lt"):
    if alpha <= 0.01 or scale <= 0.01: return
    if abs(scale - 1) > 0.01:
        sp = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.BILINEAR)
    if alpha < 0.99:
        a = sp.getchannel("A").point(lambda v: int(v * alpha)); sp = sp.copy(); sp.putalpha(a)
    ox = {"l": 0, "m": sp.width / 2, "r": sp.width}[anchor[0]]; oy = {"t": 0, "m": sp.height / 2, "b": sp.height}[anchor[1]]
    comp(base, sp, x - ox, y - oy)


def comp(base, lay, x, y):
    """화면 밖으로 일부 나가도 되는 합성."""
    x, y = int(x), int(y); l, t = max(0, -x), max(0, -y); r, b = min(lay.width, W - x), min(lay.height, H - y)
    if r > l and b > t: base.alpha_composite(lay.crop((l, t, r, b)), (x + l, y + t))


def rr(base, box, r, fill):
    """반투명까지 되는 둥근 사각형 (RGBA 화면에 바로 그리면 투명도가 섞이지 않음)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    if x1 - x0 < 2 or y1 - y0 < 2 or (len(fill) == 4 and fill[3] <= 0): return
    lay = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), min(r, (y1 - y0) // 2, (x1 - x0) // 2), fill=fill if len(fill) == 4 else fill + (255,))
    comp(base, lay, x0, y0)


def T(base, text, x, y, size, color=FG, weight="ExtraBold", scale=1.0, alpha=1.0, anchor="lt"):
    put(base, sprite(text, weight, size, color), x, y, scale, alpha, anchor)


def pct(x): return f"{'+' if x > 0 else ''}{x:.2f}%"
def eok(x):
    n = abs(round(x)); j, r = divmod(n, 10000); sg = "+" if x > 0 else "-" if x < 0 else ""
    return sg + (f"{j}조 {r:,}억" if j and r else f"{j}조" if j else f"{n:,}억")
def col(x): return RED if x > 0 else BLUE if x < 0 else FG


# ---------- 배경 ----------
def make_bg() -> Image.Image:
    g = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(g)
    for y in range(H):
        t = y / H; d.line([(0, y), (W, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)) + (255,))
    return g


GRIDL = None


def bg_at(BG, t, mood):
    global GRIDL
    if GRIDL is None:
        GRIDL = Image.new("RGBA", (W + 90, H + 90), (0, 0, 0, 0)); g = ImageDraw.Draw(GRIDL)
        for x in range(0, W + 90, 90): g.line([(x, 0), (x, H + 90)], fill=(20, 30, 60, 14))
        for y in range(0, H + 90, 90): g.line([(0, y), (W + 90, y)], fill=(20, 30, 60, 14))
    im = BG.copy(); off = int(t * 40) % 90  # 천천히 흐르는 모눈
    im.alpha_composite(GRIDL.crop((90 - off, 90 - off, 90 - off + W, 90 - off + H)))
    # 화면을 가로지르며 그려지는 차트 선 (그날 분위기 색)
    c = RED if mood >= 0 else BLUE; n = int(clamp(t / 4) * 60) + 2
    pts = [(i / 60 * W, 1500 - (1 if mood >= 0 else -1) * i * 6 + 60 * math.sin(i * 0.5 + t)) for i in range(n)]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(lay).line(pts, fill=c + (45,), width=6)
    im.alpha_composite(lay)
    return im


# ---------- 장면 ----------
def photo_fill(hid):
    ph = Image.open(TEAM_IMG / f"{hid}.jpg").convert("RGB")
    ph = ph.resize((W, round(ph.height * W / ph.width)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 80, 2))
    ph = ph.crop((0, 40, W, 40 + H)) if ph.height >= H + 40 else ph.resize((W, H), Image.LANCZOS)
    shade = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(shade)
    for y in range(H):
        t = max(0, 1 - y / 560) if y < 560 else max(0, (y - 820) / (H - 820))
        sd.line([(0, y), (W, y)], fill=int(235 * min(1, t) ** 1.2))
    return Image.composite(Image.new("RGB", (W, H), BG1), ph, shade).convert("RGBA")  # 위아래는 밝은 바탕으로


def s_cover(im, t, R, md, PH):
    z = 1.22 - 0.17 * out3(prog(t, 0, 3.6))  # 확대 → 축소 (줌아웃)
    zw, zh = int(W * z), int(H * z); p = PH.resize((zw, zh), Image.BILINEAR)
    im.alpha_composite(p.crop(((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H)))
    a = prog(t, 0.05, 0.4); T(im, f"AI 투자연구소 · {md} 장마감", 60 - 300 * (1 - out3(a)), 60, 38, FG, "Bold", alpha=a)
    # 첫 1초가 승부 (2026-10-30): 첫 장면부터 큰 등락률이 화면 가득 '쾅' → 0.3초 만에 제자리로 줄어듦
    b = R["big"]; a = prog(t, 0.0, 0.3); e = out3(a)
    sp = sprite(f"{b['name']} {pct(b['chg'])}", "ExtraBold", 96, col(b["chg"]))
    s0 = min(2.1, 0.92 * W / sp.width); sc = s0 - (s0 - 1) * e  # 화면 폭을 넘지 않게
    x = 58 * e + (W - sp.width * sc) / 2 * (1 - e); y = 130 + 520 * (1 - e)
    if e > 0.97: rr(im, (50, 150, 50 + sp.width + 20, 150 + sp.height - 10), 14, YEL + (230,))  # 형광펜 (자리 잡은 뒤)
    put(im, sp, x, y, scale=sc)
    a = prog(t, 0.3, 0.4)
    T(im, "왜 올랐을까?" if b["chg"] > 0 else "왜 빠졌을까?", 58, 250, 112, FG, scale=1 + 0.6 * (1 - back(a)) if a < 1 else 1, alpha=a)
    a = prog(t, 0.7, 0.6); d = ImageDraw.Draw(im); d.rectangle((60, 392, 60 + int(560 * out3(a)), 404), fill=ACC)  # 밑줄 그어지기
    line = f"{R['gsub']} 전해주는 오늘 장마감"; n = int(len(line) * prog(t, 1.5, 0.8))  # 한 글자씩
    if n: T(im, line[:n], 60, 1440, 48, FG, "Bold")
    for i, (lab, x) in enumerate([("코스피", R["kospi"]), ("코스닥", R["kosdaq"])]):
        a = prog(t, 2.0 + i * 0.2, 0.45); y = 1520 + 220 * (1 - out3(a))
        T(im, lab, 60 + i * 500, y, 40, DIM, "Bold", alpha=a)
        T(im, pct(x["chg"] * out3(a)), 60 + i * 500, y + 54, 100, col(x["chg"]), alpha=a)


def s_index(im, t, R, md, PH):
    a = prog(t, 0, 0.4); T(im, "오늘의 시장", 70, 210 - 80 * (1 - out3(a)), 88, FG, alpha=a)
    T(im, f"{md} 장 마감", 74, 320, 38, DIM, "Medium", alpha=prog(t, 0.2, 0.4))
    d = ImageDraw.Draw(im, "RGBA")
    for i, (lab, x) in enumerate([("코스피", R["kospi"]), ("코스닥", R["kosdaq"])]):
        a = prog(t, 0.3 + i * 0.25, 0.5); y0 = 430 + i * 360; xo = 900 * (1 - out3(a)) * (1 if i == 0 else -1)
        rr(im, (64 + xo, y0 + 8, 1024 + xo, y0 + 328), 40, (20, 30, 60, int(18 * a))); rr(im, (60 + xo, y0, 1020 + xo, y0 + 320), 40, (255, 255, 255, int(255 * a)))
        e = out3(prog(t, 0.5 + i * 0.25, 1.2))
        T(im, lab, 110 + xo, y0 + 40, 46, DIM, "Bold", alpha=a)
        T(im, f"{x['v'] * (0.9 + 0.1 * e):,.2f}", 110 + xo, y0 + 120, 64, FG, alpha=a)
        T(im, pct(x["chg"] * e), 980 + xo, y0 + 110, 110, col(x["chg"]), anchor="rt", alpha=a)
    # 상승·하락 막대가 가운데서 양쪽으로
    a = out3(prog(t, 1.4, 1.0)); n = max(R["n"], 1); y = 1250
    T(im, f"{R['n']}종목 중", W // 2, y - 90, 42, DIM, "Bold", anchor="mt", alpha=prog(t, 1.3, 0.3))
    wu = int(860 * R["up"] / n * a); wd = int(860 * R["dn"] / n * a)  # 왼쪽 끝에서 오른쪽으로 차오름
    rr(im, (110, y, 110 + wu, y + 70), 18, RED); rr(im, (110 + wu + 6, y, 110 + wu + 6 + wd, y + 70), 18, BLUE)
    T(im, f"상승 {round(R['up'] * a)}", 110, y + 110, 54, RED, alpha=a)
    T(im, f"하락 {round(R['dn'] * a)}", 970, y + 110, 54, BLUE, anchor="rt", alpha=a)


def s_movers(key, title, dirn):
    def f(im, t, R, md, PH):
        c = RED if key == "top" else BLUE
        a = prog(t, 0, 0.35); T(im, title, 70, 200, 92, FG, scale=1.3 - 0.3 * out3(a), alpha=a)
        T(im, "이유는 그날 뉴스·공시에서", 74, 320, 36, DIM, "Medium", alpha=prog(t, 0.2, 0.4))
        d = ImageDraw.Draw(im, "RGBA")
        for i, m in enumerate(R[key]):
            a = prog(t, 0.35 + i * 0.3, 0.5); e = out3(a); xo = dirn * 1100 * (1 - e); y0 = 450 + i * 420
            rr(im, (64 + xo, y0 + 8, 1024 + xo, y0 + 378), 40, (20, 30, 60, int(18 * a))); rr(im, (60 + xo, y0, 1020 + xo, y0 + 370), 40, (255, 255, 255, int(255 * a)))
            rr(im, (60 + xo, y0, 76 + xo, y0 + 370), 8, c + (int(255 * a),))
            T(im, f"{i + 1}", 110 + xo, y0 + 40, 56, c, alpha=a)
            T(im, m["name"], 190 + xo, y0 + 42, 58, FG, alpha=a)
            T(im, pct(m["chg"] * out3(prog(t, 0.5 + i * 0.3, 0.9))), 980 + xo, y0 + 150, 96, col(m["chg"]), anchor="rt", alpha=a)
            why = (m.get("why") or "뚜렷한 개별 소식은 없었어요")
            why = why if len(why) <= 24 else why[:23] + "…"
            T(im, why, 110 + xo, y0 + 290, 36, DIM, "Medium", alpha=prog(t, 0.8 + i * 0.3, 0.4))
    return f


def s_flow(im, t, R, md, PH):
    a = prog(t, 0, 0.35); T(im, "누가 사고 팔았나", 70, 200, 88, FG, alpha=a, scale=1.3 - 0.3 * out3(a))
    T(im, "코스피 · 순매수(빨강) / 순매도(파랑)", 74, 320, 36, DIM, "Medium", alpha=prog(t, 0.2, 0.4))
    v = R["flow"].get("KOSPI") or {"frg": 0, "org": 0, "ind": 0}; mx = max(abs(v["frg"]), abs(v["org"]), abs(v["ind"]), 1)
    d = ImageDraw.Draw(im, "RGBA")
    for i, (who, k) in enumerate([("외국인", "frg"), ("기관", "org"), ("개인", "ind")]):
        y = 560 + i * 330; e = out3(prog(t, 0.4 + i * 0.25, 0.9)); val = v[k]; L = int(400 * abs(val) / mx * e)
        T(im, who, 70, y, 56, FG, "Bold", alpha=prog(t, 0.3 + i * 0.25, 0.3))
        rr(im, (538, y + 100, 542, y + 200), 1, (20, 30, 60, 60))
        if val >= 0: rr(im, (540, y + 110, 540 + max(L, 4), y + 190), 20, RED)
        else: rr(im, (540 - max(L, 4), y + 110, 540, y + 190), 20, BLUE)
        T(im, eok(val * e), 1010, y, 60, col(val), anchor="rt", alpha=prog(t, 0.4 + i * 0.25, 0.3))


def s_cta(im, t, R, md, PH, AV):
    a = prog(t, 0, 0.5); s = back(a) if a < 1 else 1
    if s > 0.05:
        av = AV.resize((int(360 * s), int(360 * s)), Image.BILINEAR); im.alpha_composite(av, (540 - av.width // 2, 330 - av.height // 2 + 200))
    T(im, f"오늘은 {R['gsub']} 전해 드렸어요", W // 2, 800, 52, FG, anchor="mt", alpha=prog(t, 0.3, 0.4))
    T(im, "평일 17시 50분, 장마감 1분 요약", W // 2, 880, 40, DIM, "Medium", anchor="mt", alpha=prog(t, 0.45, 0.4))
    d = ImageDraw.Draw(im, "RGBA"); a = prog(t, 0.6, 0.4)
    pulse = 1 + 0.04 * math.sin(max(0, t - 1.0) * 7) if t > 1.0 else back(a) if a < 1 else 1
    bw, bh = int(900 * pulse), int(230 * pulse); x0, y0 = 540 - bw // 2, 1080 - bh // 2 + 120
    if a > 0: rr(im, (x0, y0, x0 + bw, y0 + bh), 40, RED + (int(255 * a),))
    T(im, f"무료 {R.get('app', '모의투자앱')} 드려요", W // 2, y0 + 45 * pulse, 46, WHITE, "Bold", scale=pulse, anchor="mt", alpha=a)
    T(im, "팔로우하고 '연구소' 남겨주세요", W // 2, y0 + 115 * pulse, 56, WHITE, scale=pulse, anchor="mt", alpha=a)
    a = prog(t, 1.0, 0.4)
    if a: rr(im, (340, 1520, 740, 1620), 50, FG + (int(255 * a),))
    T(im, "팔로우하기", W // 2, 1570, 46, WHITE, anchor="mm", alpha=a)


def build(web: Path) -> Path | None:
    web = Path(web); cd = web / "data" / "cards"
    info = json.loads((cd / "cards.json").read_text(encoding="utf-8"))
    R = info.get("reel")
    if not R: print("[릴스] cards.json 에 reel 자료가 없음 → 건너뜀"); return None
    date = info["date"]; md = f"{int(date[5:7])}월 {int(date[8:])}일"; mood = R["kospi"]["chg"]
    BG = make_bg(); PH = photo_fill(info["host"])
    av = Image.open(TEAM_IMG / f"{info['host']}.jpg").convert("RGB"); sz = min(av.size)
    av = av.crop(((av.width - sz) // 2, 0, (av.width - sz) // 2 + sz, sz)).resize((360, 360), Image.LANCZOS)
    m = Image.new("L", (360, 360), 0); ImageDraw.Draw(m).ellipse((0, 0, 359, 359), fill=255)
    AV = Image.new("RGBA", (360, 360), (0, 0, 0, 0)); AV.paste(av, (0, 0), m)
    ImageDraw.Draw(AV).ellipse((2, 2, 357, 357), outline=ACC + (255,), width=8)
    fns = [s_cover, s_index, s_movers("top", "많이 오른 종목", 1), s_movers("bottom", "많이 내린 종목", -1), s_flow,
           lambda im, t, R, md, PH: s_cta(im, t, R, md, PH, AV)]
    starts = [sum(SCENES[:i]) for i in range(len(SCENES))]; total = sum(SCENES)

    def scene(k, t):
        im = bg_at(BG, t + starts[k], mood); fns[k](im, t, R, md, PH)
        seg = (W - 80 - 10 * (len(SCENES) - 1)) / len(SCENES)
        for i in range(len(SCENES)):
            x0 = 40 + i * (seg + 10); fill = 1 if i < k else clamp(t / SCENES[k]) if i == k else 0
            rr(im, (x0, 22, x0 + seg, 30), 4, (20, 30, 60, 40))
            if fill: rr(im, (x0, 22, x0 + seg * fill, 30), 4, FG + (230,))
        T(im, f"{md} 장 마감 기준 · 참고용, 투자 권유 아님", W // 2, H - 40, 26, DIM, "Medium", anchor="mb")
        return im

    def zoomed(im, z, alpha=1.0):
        zw, zh = int(W * z), int(H * z); p = im.resize((zw, zh), Image.BILINEAR)
        p = p.crop(((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H)) if z >= 1 else p
        out = Image.new("RGBA", (W, H), BG1 + (255,))
        out.alpha_composite(p, ((W - p.width) // 2, (H - p.height) // 2)) if z < 1 else out.alpha_composite(p)
        if alpha < 1: out.putalpha(int(255 * alpha))
        return out

    audio = web / "app" / "bgm" / "main.mp3"
    args = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio.exists(): args += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-af", f"afade=t=in:d=0.4,afade=t=out:st={total - 1.2:.2f}:d=1.2", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    args += ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(cd / "reel.mp4")]
    pr = subprocess.Popen(args, stdin=subprocess.PIPE)
    for fi in range(int(total * FPS)):
        tt = fi / FPS; k = max(i for i in range(len(starts)) if starts[i] <= tt); t = tt - starts[k]
        if k > 0 and t < TR:  # 전환: 앞 장면은 커지며 사라지고, 새 장면은 작은 데서 커지며 들어옴
            e = out3(t / TR)
            prev = zoomed(scene(k - 1, SCENES[k - 1] - 0.001), 1 + 0.25 * e)
            cur = zoomed(scene(k, t), 0.88 + 0.12 * e)
            fr = Image.blend(prev, cur, e)
        else:
            fr = scene(k, t)
        if fi == int(1.6 * FPS): fr.convert("RGB").save(cd / "reel_cover.jpg", quality=90)
        pr.stdin.write(fr.convert("RGB").tobytes())
    pr.stdin.close(); pr.wait()
    if pr.returncode: raise SystemExit(f"ffmpeg 실패 {pr.returncode}")
    return cd / "reel.mp4"


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "web")))
