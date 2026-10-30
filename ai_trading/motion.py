"""릴스 모션그래픽 (2026-10-25 사용자: "보라 배경 없애고, 인물이 날아오고 글씨가 확대되는 세련된 릴스").

밝은 무채색 바탕 + 검정 글씨 + 파랑 포인트 하나 + 노란 형광펜. 장면마다 요소가 시간차로 등장한다.
- 인물 사진: 옆에서 날아 들어오며 살짝 기울었다 바로 섬 (easeOutBack)
- 큰 글씨: 크게 시작해 제자리로 줄어들며 나타남 / 줄마다 아래에서 올라오며 나타남
- 숫자: 0부터 올라가며 세짐
- 앱 화면: 휴대폰이 아래에서 올라온 뒤 천천히 스크롤
- 장면 사이: 위로 밀리며 사라짐
프레임을 바로 JPG로 써서 메모리를 아낀다. 1080x1920, 30fps.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ai_trading.data.cards import FONT, _photo, _wrap

W, H, FPS = 1080, 1920, 30
BG = (246, 245, 241)
INK = (20, 22, 30)
MUTED = (112, 116, 128)
BLUE = (38, 99, 235)
MARK = (255, 224, 102)
WHITE = (255, 255, 255)
GRID = (236, 235, 230)
WAVE = (212, 222, 245)


def set_theme(th: dict):
    """그 주의 색 (cards.theme_of 와 같은 것): 바탕·모눈·포인트 색. 장식 선은 포인트 색을 바탕에 옅게 섞음."""
    global BG, GRID, BLUE, WAVE
    BG, GRID, BLUE = tuple(th["paper"]), tuple(th["grid"]), tuple(th["acc"])
    WAVE = tuple(int(p * 0.78 + a * 0.22) for p, a in zip(BG, BLUE))
    _paper.cache_clear(); text.cache_clear()


# ---------- 시간 곡선 ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3
def in_cubic(t): t = clamp(t); return t ** 3
def in_out(t): t = clamp(t); return t * t * (3 - 2 * t)
def out_back(t, s=1.6): t = clamp(t) - 1; return 1 + (s + 1) * t ** 3 + s * t ** 2
def prog(f, start, dur): return clamp((f - start) / max(1, dur))


# ---------- 글자·그림 층 ----------
@lru_cache(maxsize=64)
def font(w: str, s: int):
    return ImageFont.truetype(str(FONT / f"Pretendard-{w}.otf"), s)


def wrapw(text: str, f, width: int) -> list[str]:
    """띄어쓰기 단위 줄바꿈 (숫자·단어가 중간에 잘리지 않게)."""
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width: cur = t; continue
        if cur: lines.append(cur)
        cur = w
        if d.textlength(w, font=f) > width:
            parts = _wrap(d, w, f, width); lines += parts[:-1]; cur = parts[-1]
    return lines + ([cur] if cur else [])


@lru_cache(maxsize=256)
def text(s: str, size: int, w: str = "ExtraBold", color=INK) -> Image.Image:
    f = font(w, size); d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), s, font=f)
    im = Image.new("RGBA", (r - l + 8, int(size * 1.25)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, int(size * 0.1)), s, font=f, fill=color)
    return im


def pill(s: str, size=40, fg=WHITE, bg=INK, pad=(34, 16)) -> Image.Image:
    t = text(s, size, "Bold", fg)
    im = Image.new("RGBA", (t.width + pad[0] * 2, t.height + pad[1] * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=bg)
    im.alpha_composite(t, (pad[0], pad[1]))
    return im


def shadowed(img: Image.Image, mask: Image.Image | None = None, r=40, blur=28, off=18, op=70) -> Image.Image:
    """사진·휴대폰 아래 부드러운 그림자."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
        if mask is not None: img.putalpha(mask)
    m = img.getchannel("A")
    sh = Image.new("RGBA", (img.width + blur * 4, img.height + blur * 4), (0, 0, 0, 0))
    s = Image.new("RGBA", img.size, (20, 22, 40, op)); s.putalpha(m.point(lambda a: a * op // 255))
    sh.alpha_composite(s, (blur * 2, blur * 2 + off)); sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(img, (blur * 2, blur * 2))
    return sh


def put(fr: Image.Image, layer: Image.Image, cx: float, cy: float, scale=1.0, alpha=1.0, rot=0.0):
    """층을 (cx, cy) 가운데에 크기·투명도·기울기를 줘서 얹는다."""
    if alpha <= 0.01 or scale <= 0.01: return
    L = layer
    if abs(scale - 1) > 0.003: L = L.resize((max(1, int(L.width * scale)), max(1, int(L.height * scale))), Image.BILINEAR)
    if abs(rot) > 0.05: L = L.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = L.getchannel("A").point(lambda v: int(v * alpha)); L = L.copy(); L.putalpha(a)
    x, y = int(cx - L.width / 2), int(cy - L.height / 2)
    fr.alpha_composite(L, (x, y))


def put_left(fr, layer, x, cy, **k):
    put(fr, layer, x + layer.width * k.get("scale", 1.0) / 2, cy, **k)


# ---------- 바탕 ----------
@lru_cache(maxsize=1)
def _paper() -> Image.Image:
    im = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=GRID + (255,), width=1)  # 아주 옅은 모눈 (차트 종이 느낌)
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=GRID + (255,), width=1)
    return im


def base(f: int, brand=True) -> Image.Image:
    fr = _paper().copy()
    d = ImageDraw.Draw(fr)
    # 천천히 흐르는 얇은 차트 선 (장식)
    pts = [(x, 1560 + 50 * math.sin(x / 140 + f / 22) + 26 * math.sin(x / 57 - f / 15)) for x in range(-20, W + 40, 20)]
    d.line(pts, fill=WAVE + (255,), width=5)
    if brand:
        d.rounded_rectangle((60, 70, 72, 82), 3, fill=BLUE)
        d.text((86, 76), "AI 투자연구소", font=font("Bold", 30), fill=INK, anchor="lm")
    return fr


# ---------- 장면 ----------
class Reel:
    def __init__(self, out: Path):
        self.out = Path(out); self.out.mkdir(parents=True, exist_ok=True); self.n = 0; self.cover = None
        self.overlay = None  # 모든 프레임 위에 고정으로 얹는 층 (구석 스티커 등)

    def emit(self, fr: Image.Image):
        if self.overlay is not None: fr.alpha_composite(self.overlay)
        fr.convert("RGB").save(self.out / f"{self.n:04d}.jpg", quality=88); self.n += 1

    def scene(self, frames: int, draw, exit_frames=7):
        """draw(fr, f) 로 그린 뒤, 마지막 몇 프레임은 위로 밀리며 사라짐."""
        for f in range(frames):
            fr = base(self.n)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw(layer, f)
            k = prog(f, frames - exit_frames, exit_frames)
            if k > 0:
                e = in_cubic(k); a = layer.getchannel("A").point(lambda v: int(v * (1 - e))); layer.putalpha(a)
                fr.alpha_composite(layer, (0, int(-160 * e)))
            else:
                fr.alpha_composite(layer)
            self.emit(fr)
            if self.cover is None and f == frames - exit_frames - 1: self.cover = fr.convert("RGB")


def hook(R: Reel, lines: list[str], host, tag: str, sec=2.4):
    hid, hname, hrole = host
    ph, m = _photo(hid, 700, 880, 52); photo = shadowed(ph, m)
    tg = pill(tag, 38, WHITE, BLUE)
    size = 124 if max(len(x) for x in lines) <= 7 else 104
    T = [text(s, size) for s in lines]
    nm = pill(f"{hname} · {hrole}", 36, INK, WHITE)
    top = 250

    def draw(fr, f):
        put_left(fr, tg, 70, top, scale=out_back(prog(f, 0, 9)), alpha=prog(f, 0, 4))
        for i, t in enumerate(T):  # 글자: 크게 시작해 제자리로
            p = prog(f, 3 + i * 4, 10); put_left(fr, t, 64, top + 120 + i * int(size * 1.18), scale=1 + 0.35 * (1 - out_cubic(p)), alpha=out_cubic(p))
        p = prog(f, 9, 16); x = W + 460 - (W + 460 - (W - 420)) * out_back(p, 1.3)  # 인물: 오른쪽에서 날아옴
        put(fr, photo, x, 1230, rot=8 * (1 - out_cubic(p)))
        p = prog(f, 22, 10); put(fr, nm, W - 420, 1735 + 60 * (1 - out_cubic(p)), alpha=out_cubic(p))
    R.scene(int(sec * FPS), draw)


def lines_scene(R: Reel, label: str, body: str, sec: float, big: str = "", highlight_first=True, avatar=None):
    """제목 + (큰 용어) + 본문 줄이 하나씩 올라오며 등장, 첫 줄에 형광펜."""
    lab = pill(label, 36, WHITE, INK)
    bigL = text(big, 210, "ExtraBold", BLUE) if big else None
    for size in (92, 86, 80, 74, 68, 62):
        ls = wrapw(body, font("ExtraBold", size), W - 150)
        if len(ls) * size * 1.38 <= (820 if big else 1150): break
    L = [text(s, size) for s in ls]; lh = int(size * 1.38)
    block = len(L) * lh + (380 if big else 0)                  # 화면 세로 가운데쯤 오게
    top = max(420, (H - block) // 2 - 80); bigy = top + 120; y0 = top + (260 if big else 0) - (120 if big else 0)
    av = None
    if avatar:
        ph, m = _photo(avatar, 180, 180, 90); av = shadowed(ph, m, blur=14, off=8)

    def draw(fr, f):
        put_left(fr, lab, 70, 250, scale=out_back(prog(f, 0, 9)), alpha=prog(f, 0, 4))
        if bigL is not None:
            p = prog(f, 2, 12); put_left(fr, bigL, 58, bigy, scale=1 + 0.6 * (1 - out_cubic(p)), alpha=out_cubic(p))
        d = ImageDraw.Draw(fr)
        for i, t in enumerate(L):
            p = prog(f, 8 + i * 4, 10); y = y0 + i * lh + (120 if big else 0)
            if highlight_first and i == 0:  # 형광펜이 왼쪽에서 그어짐
                q = in_out(prog(f, 16, 12)); x1 = 66 + (t.width - 4) * q
                if q > 0: d.rounded_rectangle((66, y + int(size * 0.55), x1, y + int(size * 1.05)), 8, fill=MARK + (255,))
            put_left(fr, t, 62, y + size * 0.62 + 50 * (1 - out_cubic(p)), alpha=out_cubic(p))
        if av is not None:
            p = prog(f, 14, 14); put(fr, av, W - 150 + 300 * (1 - out_back(p, 1.2)), 1720, alpha=prog(f, 14, 4))
    R.scene(int(sec * FPS), draw)


def number_scene(R: Reel, label: str, value: str, sec: float, foot: str = "공개 자료 · 참고용"):
    """오늘 실제 숫자: 숫자 부분이 0부터 올라가며 세지고 크게 튀어나옴."""
    lab = pill(label, 36, WHITE, INK)
    paren = re.search(r"\s*\([^)]*\)\s*$", value)          # 끝의 (날짜)는 숫자로 세지 않고 아래 작은 글씨로
    core, note = (value[:paren.start()], paren.group(0).strip()) if paren else (value, "")
    m = re.search(r"[-+]?\d[\d,]*\.?\d*", core)
    head, num_s, tail = (core[:m.start()], m.group(0), core[m.end():]) if m else (core, "", "")
    tail = (tail.strip() + " " + note).strip()
    target = float(num_s.replace(",", "")) if num_s else 0
    dec = len(num_s.split(".")[1]) if "." in num_s else 0
    H1 = [text(s, 64, "Bold", MUTED) for s in wrapw(head.strip(), font("Bold", 64), W - 150)] if head.strip() else []
    tail_parts = tail.strip().split(" ", 1)
    unit = tail_parts[0] if tail_parts and len(tail_parts[0]) <= 3 else ""
    rest = tail.strip()[len(unit):].strip()
    R2 = [text(s, 56, "Medium", MUTED) for s in wrapw(rest, font("Medium", 56), W - 150)] if rest else []
    ft = text(foot, 34, "Medium", MUTED)

    def draw(fr, f):
        put_left(fr, lab, 70, 250, scale=out_back(prog(f, 0, 9)), alpha=prog(f, 0, 4))
        for i, t in enumerate(H1):
            p = prog(f, 4 + i * 3, 9); put_left(fr, t, 64, 700 + i * 86 + 30 * (1 - out_cubic(p)), alpha=out_cubic(p))
        if num_s:
            p = prog(f, 8, 22); v = target * out_cubic(p)
            sgn = "+" if num_s.startswith("+") and v > 0 else ""
            s = sgn + (f"{v:,.{dec}f}" if "," in num_s or abs(target) >= 1000 else f"{v:.{dec}f}") + unit
            n = text(s, 230, "ExtraBold", BLUE)
            put_left(fr, n, 54, 1020, scale=1 + 0.25 * (1 - out_back(prog(f, 8, 12), 1.4)), alpha=prog(f, 8, 4))
        for i, t in enumerate(R2):
            p = prog(f, 20 + i * 3, 9); put_left(fr, t, 64, 1220 + i * 80, alpha=out_cubic(p))
        put_left(fr, ft, 70, 1820, alpha=prog(f, 18, 8))
    R.scene(int(sec * FPS), draw)


def phone_scene(R: Reel, shot: Path, cap: str, sec: float, side=1):
    """휴대폰이 아래(또는 옆)에서 올라온 뒤 화면이 천천히 스크롤."""
    s = Image.open(shot).convert("RGB")
    pw, ph_h = 760, 1300; s = s.resize((pw, int(s.height * pw / s.width)), Image.LANCZOS)
    top1 = max(0, min(s.height - ph_h, 480))
    mask = Image.new("L", (pw, ph_h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph_h - 1), 56, fill=255)
    frame = Image.new("RGBA", (pw + 28, ph_h + 28), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, pw + 27, ph_h + 27), 70, fill=INK)
    sh = shadowed(frame, blur=30, off=24, op=90)
    capL = [text(x, 68) for x in wrapw(cap, font("ExtraBold", 68), W - 140)]
    n = int(sec * FPS)

    def draw(fr, f):
        for i, t in enumerate(capL):
            p = prog(f, i * 3, 10); put_left(fr, t, 64, 230 + i * 90, scale=1 + 0.25 * (1 - out_cubic(p)), alpha=out_cubic(p))
        p = out_back(prog(f, 2, 16), 1.1)
        cx = W / 2 + side * 500 * (1 - p); cy = 1110 + 700 * (1 - p) * (0.4 if side else 1)
        k = in_out(prog(f, 18, n - 26)); top = int(top1 * k)
        scr = s.crop((0, top, pw, top + ph_h)).convert("RGBA"); scr.putalpha(mask)
        ph = sh.copy(); off = (ph.width - frame.width) // 2
        ph.alpha_composite(scr, (off + 14, off + 14))
        put(fr, ph, cx, cy, scale=0.92 + 0.08 * p, rot=side * 6 * (1 - out_cubic(prog(f, 2, 16))))
    R.scene(n, draw)


def end_scene(R: Reel, lines=("남기면 DM으로", "바로 보내 드려요"), sub=("실제 거래소 종가 그대로", "가상 돈으로 하는 연습용 게임"), md="", sec=2.2):
    t1 = text("댓글에", 80, "Bold", MUTED)
    kw = text("'연구소'", 200, "ExtraBold", BLUE)
    L = [text(x, 76) for x in lines]
    btn = pill("팔로워 선공개", 46, WHITE, INK, pad=(54, 24))
    S = [text(x, 44, "Medium", MUTED) for x in sub]
    ft = text(f"{md} 장 마감 기준 · 투자 권유 아님" if md else "투자 권유 아님", 32, "Medium", MUTED)

    def draw(fr, f):
        put(fr, t1, W / 2, 420, alpha=prog(f, 0, 6))
        p = prog(f, 3, 12); put(fr, kw, W / 2, 600, scale=1.7 - 0.7 * out_back(p, 1.5), alpha=prog(f, 3, 4))
        for i, t in enumerate(L):
            p = prog(f, 10 + i * 4, 9); put(fr, t, W / 2, 820 + i * 100 + 40 * (1 - out_cubic(p)), alpha=out_cubic(p))
        p = prog(f, 20, 12); put(fr, btn, W / 2, 1130, scale=out_back(p, 2.0), alpha=prog(f, 20, 3))
        for i, t in enumerate(S):
            put(fr, t, W / 2, 1300 + i * 66, alpha=prog(f, 26 + i * 3, 8))
        put(fr, ft, W / 2, 1830, alpha=prog(f, 26, 8))
    R.scene(int(sec * FPS), draw, exit_frames=1)


def split_q(q: str) -> list[str]:
    w = q.split(" ")
    if len(q) <= 8 or len(w) == 1: return [q]
    i = min(range(1, len(w)), key=lambda k: abs(len(" ".join(w[:k])) - len(" ".join(w[k:]))))
    return [" ".join(w[:i]), " ".join(w[i:])]


# ---------- 앱 홍보 릴스 (10/30 "드디어 공개합니다": 훅 → 기능 5개 2초씩 → 팔로우 안내) ----------
def sticker(text_s: str) -> Image.Image:
    """영상 전체 오른쪽 위에 고정되는 스티커."""
    pl = pill(text_s, 30, INK, MARK, pad=(26, 12))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); lay.alpha_composite(pl, (W - 60 - pl.width, 52))
    return lay


def promo_hook(R: Reel, lines: list[str], reason: str, host, tag: str, sec=2.6):
    """첫 문장 훅: 큰 글씨 + 이유 한 줄 + 진행자."""
    hid, hname, hrole = host
    ph, m = _photo(hid, 700, 880, 52); photo = shadowed(ph, m)
    tg = pill(tag, 38, WHITE, BLUE)
    size = 150
    T = [text(s, size) for s in lines]
    why = [text(s, 50, "Bold", MUTED) for s in wrapw(reason, font("Bold", 50), W - 140)]
    nm = pill(f"{hname} · {hrole}", 36, INK, WHITE)
    top = 250; ry = top + 140 + len(T) * int(size * 1.18) + 30

    def draw(fr, f):
        put_left(fr, tg, 70, top, scale=out_back(prog(f, 0, 9)), alpha=prog(f, 0, 4))
        for i, t in enumerate(T):
            p = prog(f, 3 + i * 4, 10); put_left(fr, t, 64, top + 140 + i * int(size * 1.18), scale=1 + 0.35 * (1 - out_cubic(p)), alpha=out_cubic(p))
        d = ImageDraw.Draw(fr)
        for i, t in enumerate(why):
            p = prog(f, 14 + i * 4, 10); put_left(fr, t, 66, ry + i * 68 + 30 * (1 - out_cubic(p)), alpha=out_cubic(p))
        p = prog(f, 12, 16); x = W + 360 - (W + 360 - (W - 330)) * out_back(p, 1.3)
        put(fr, photo, x, 1450, scale=0.72, rot=8 * (1 - out_cubic(p)))
        p = prog(f, 24, 10); put(fr, nm, W - 330, 1835 + 40 * (1 - out_cubic(p)), alpha=out_cubic(p))
    R.scene(int(sec * FPS), draw)


def feature_scene(R: Reel, shot: Path, cap: str, step: str, sec: float = 2.0, side=1):
    """기능 하나: 휴대폰 화면이 빨리 올라오고, 아래쪽 색 띠 안에 큰 자막이 뜸."""
    s = Image.open(shot).convert("RGB")
    pw, ph_h = 740, 1230; s = s.resize((pw, int(s.height * pw / s.width)), Image.LANCZOS)
    top1 = max(0, min(s.height - ph_h, 260))
    mask = Image.new("L", (pw, ph_h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph_h - 1), 56, fill=255)
    frame = Image.new("RGBA", (pw + 28, ph_h + 28), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, pw + 27, ph_h + 27), 70, fill=INK)
    sh = shadowed(frame, blur=30, off=24, op=90)
    stp = pill(step, 36, WHITE, INK)
    size = 76
    for size in (76, 68, 60):
        capL = [text(x, size, "ExtraBold", WHITE) for x in wrapw(cap, font("ExtraBold", size), W - 150)]
        if len(capL) <= 2: break
    bh = 80 + len(capL) * int(size * 1.25)
    band = Image.new("RGBA", (W, bh), (0, 0, 0, 0)); ImageDraw.Draw(band).rounded_rectangle((40, 0, W - 41, bh - 1), 44, fill=BLUE)
    n = int(sec * FPS)

    def draw(fr, f):
        put_left(fr, stp, 70, 215, scale=out_back(prog(f, 0, 8)), alpha=prog(f, 0, 3))
        p = out_back(prog(f, 0, 12), 1.1)
        cx = W / 2 + side * 420 * (1 - p); cy = 880 + 600 * (1 - p) * 0.4
        k = in_out(prog(f, 10, n - 22)); top = int(top1 * k)
        scr = s.crop((0, top, pw, top + ph_h)).convert("RGBA"); scr.putalpha(mask)
        ph = sh.copy(); off = (ph.width - frame.width) // 2
        ph.alpha_composite(scr, (off + 14, off + 14))
        put(fr, ph, cx, cy, scale=0.94 + 0.06 * p, rot=side * 5 * (1 - out_cubic(prog(f, 0, 12))))
        q = prog(f, 3, 10); by = H - 120 - bh / 2
        put(fr, band, W / 2, by + 90 * (1 - out_cubic(q)), alpha=out_cubic(q))
        for i, t in enumerate(capL):
            r = prog(f, 6 + i * 3, 9); put(fr, t, W / 2, by - bh / 2 + 40 + int(size * 1.25) * (i + 0.5) + 30 * (1 - out_cubic(r)), alpha=out_cubic(r))
    R.scene(n, draw, exit_frames=4)


def follow_button() -> Image.Image:
    """팔로우 버튼 그림: 사람 모양 + 플러스 + '팔로우'."""
    w, h = 520, 150
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=BLUE)
    d.ellipse((50, 34, 90, 74), fill=WHITE); d.rounded_rectangle((38, 80, 102, 116), 18, fill=WHITE)   # 사람
    d.rectangle((128, 66, 160, 78), fill=WHITE); d.rectangle((138, 56, 150, 88), fill=WHITE)            # +
    im.alpha_composite(text("팔로우", 64, "ExtraBold", WHITE), (190, 24))
    return im


def promo_end(R: Reel, sec=2.4):
    """마지막 장면: 팔로우 버튼 → 댓글에 '연구소' 남기면 끝! DM으로 앱 보내 드려요."""
    btn = follow_button()
    t1 = text("댓글에", 80, "Bold", MUTED)
    kw = text("'연구소'", 190, "ExtraBold", BLUE)
    t2 = text("남기면 끝!", 96)
    t3 = text("DM으로 앱 보내 드려요", 62, "ExtraBold")
    ft = text("가상 돈으로 하는 연습용 게임 · 투자 권유 아님", 32, "Medium", MUTED)

    def draw(fr, f):
        p = prog(f, 0, 12); put(fr, btn, W / 2, 400, scale=out_back(p, 2.0), alpha=prog(f, 0, 3))
        put(fr, t1, W / 2, 640, alpha=prog(f, 8, 6))
        p = prog(f, 10, 12); put(fr, kw, W / 2, 800, scale=1.7 - 0.7 * out_back(p, 1.5), alpha=prog(f, 10, 4))
        p = prog(f, 18, 9); put(fr, t2, W / 2, 1010 + 40 * (1 - out_cubic(p)), alpha=out_cubic(p))
        p = prog(f, 24, 9); put(fr, t3, W / 2, 1150 + 40 * (1 - out_cubic(p)), alpha=out_cubic(p))
        put(fr, ft, W / 2, 1830, alpha=prog(f, 26, 8))
    R.scene(int(sec * FPS), draw, exit_frames=1)
