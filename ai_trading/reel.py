"""인스타 릴스 자동 제작 (주 2회: 화·목, 15초 세로 1080x1920). 2026-10-25 사용자: "릴스는 두 번만, 초보자 지표 설명도 넣고 광고에도 활용"

- 화 '30초 주식 용어': PER·VIX·CPI 같은 말을 쉽게 풀고 오늘 실제 숫자로 예시 → 앱 용어 사전 화면 (설명은 web/app/glossary.json, 앱과 같은 파일)
- 목 '앱 소개': 실제 앱 화면을 휴대폰 틀 안에서 천천히 보여 줌. 주마다 돌아가며 앱 둘러보기 → 차트·보조지표 → 알파와 대결
- 마지막 장면: 댓글에 '연구소' → DM으로 링크 (Mirr 댓글 자동 DM 규칙과 짝)
- 숫자·문구는 데이터 그대로, 수익률 자랑·종목 권유 문구는 넣지 않는다.
결과: <web>/data/reel/reel.mp4, cover.jpg, reel.json {date, kind, caption}
실행: python -m ai_trading.reel web [kind]   (앱 화면은 web/ 을 임시 서버로 띄워 찍음)
"""
from __future__ import annotations

import datetime as dt
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ai_trading.data.cards import FONT, _photo, _wrap, host_of

W, H, FPS = 1080, 1920, 30
INK, LAVD, WHITE = (45, 42, 99), (108, 92, 231), (255, 255, 255)
F = lambda w, s: __import__("PIL.ImageFont", fromlist=["x"]).truetype(str(FONT / f"Pretendard-{w}.otf"), s)

# 요일별 이야기 (화=1, 목=3, 금=4)
KINDS = {
    "tour": {"hook": ["퇴근길 5분,", "종가로만 하는", "투자 게임"],
             "shots": [("#home", "오늘 장마감을 AI 직원들이 정리"), ("#analysis", "대형주를 점수로 한눈에"), ("#game", "가상 돈으로 하루 한 번 종가 주문")]},
    "chart": {"hook": ["차트 보는 법,", "보조지표까지", "손가락으로"],
              "shots": [("#analysis/{sym}", "일·주·월봉, 두 손가락 확대"), ("#analysis/{sym}@ind", "MACD·RSI·볼린저 한 번에"), ("#home", "매일 17:50 장마감 정리")]},
    "vs": {"hook": ["AI 팀 '알파'와", "수익률 대결,", "이길 수 있을까?"],
           "shots": [("#vs", "같은 날, 같은 돈으로 시작"), ("#game", "하루 한 번, 종가로 주문"), ("#analysis", "대형주 AI 점수로 종목 고르기")]},
}
KINDS["word"] = {"hook": [], "shots": [("#learn/{term}", "용어 사전")]}
BY_WEEKDAY = {1: "word", 3: "app"}                       # 화·목
APP_KINDS = ["tour", "chart", "vs"]                      # 목요일은 주마다 돌아가며
# 용어 릴스 순서 (초보자가 많이 묻는 것부터, 주마다 하나)
WORD_ORDER = ["per", "vix", "cpi", "rate", "rsi", "pbr", "usdkrw", "roe", "ma", "flow", "macd", "us10y", "div", "bb", "wti", "vol",
              "margin", "debt", "cap", "close", "stop", "swing"]
EX = "005930.KS"
UNIT = {"per": "배", "pbr": "배", "roe": "%", "div_yield": "%", "debt": "%", "margin": "%"}


def _week(d: dt.date) -> int:
    return (d - dt.date(2026, 10, 26)).days // 7


def live(t: dict, sc: dict, facts: dict) -> str:
    """앱 learn.js 의 live() 와 같은 문장: 오늘 실제 값 한 줄."""
    k = t.get("live"); s = sc["stocks"].get(EX); d = sc["date"][5:].replace("-", ".")
    num = lambda v, n=2: f"{v:,.{n}f}".rstrip("0").rstrip(".") if n else f"{v:,.0f}"
    sgn = lambda v: ("+" if v > 0 else "") + num(v)
    try:
        if not k: return ""
        if k.startswith("fin."):
            f = k[4:]; v = s and (s.get("fin") or {}).get(f)
            return "" if v is None else f"{s['name']} {t['name']} {num(v)}{UNIT.get(f, '')} ({d})"
        if k == "VIX": return f"{d} VIX {facts['VIX']}"
        if k == "미국10년물": return f"{d} 미국 10년 금리 {facts['미국10년물']}%"
        if k == "usdkrw": return f"{d} 원/달러 {num(sc['market']['usdkrw']['v'], 1)}원"
        if k == "WTI_20일%": return f"WTI 최근 한 달 {sgn(facts['WTI_20일%'])}% ({d})"
        if k == "frg":
            m = facts["오늘_시장수급_억원"]["KOSPI"]; return f"{d} 외국인 코스피 {sgn(m['frg'])}억 · 기관 {sgn(m['org'])}억"
        if k == "ma20":
            m = next(x for x in s["tech"] if x[0] == "20일 이동평균")
            return f"{s['name']} 종가 {num(s['price'], 0)}원 · 20일선 {num(m[1], 0)}원 ({'위' if s['price'] >= m[1] else '아래'})"
    except Exception:
        return ""
    return ""


def _serve(root: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def shoot(web: Path, kind: str, sym: str, tmp: Path, term: str = "") -> list[Path]:
    """앱 화면을 휴대폰 크기(390폭)로 길게 찍는다. 처음 안내·동의 창은 미리 끝낸 상태로."""
    from playwright.sync_api import sync_playwright
    srv, port = _serve(web)
    seed = {"aiLab.consent.v1": "2026-10-25", "aiLab.team.v1": json.dumps({"dir": "theo", "staff": ["joy", "oscar", "ray", "miles", "lloyd", "nova"]}),
            "aiLab.call.v1": json.dumps("투자자님"), "aiLab.tour.v1": json.dumps({"done": True, "offered": True}), "appGuideSeen": "1",
            "aiLab.chart.v1": json.dumps({"ov": ["ma"], "sub": "none"}), "aiLab.m.v1": json.dumps({"first": "2000-01-01", "sent": {"open": "9999"}})}
    out = []
    try:
        with sync_playwright() as p:
            b = None
            for kw in ({"channel": "chrome"}, {}, {"executable_path": os.environ.get("REEL_CHROME", "/opt/pw-browsers/chromium")}):
                try:
                    b = p.chromium.launch(**kw); break
                except Exception as e:  # 크롬 → 플레이라이트 기본 → 지정 경로 순서로 시도
                    err = e
            if b is None: raise err
            ctx = b.new_context(viewport={"width": 390, "height": 760}, device_scale_factor=2.77, is_mobile=True, has_touch=True, locale="ko-KR")
            ctx.add_init_script("".join(
                f"try{{localStorage.setItem({json.dumps(k)},{json.dumps(v)})}}catch(e){{}};" for k, v in seed.items()))
            ctx.route("**/*.workers.dev/**", lambda r: r.abort())  # 집계·랭킹 서버에 찍기용 방문을 남기지 않음
            pg = ctx.new_page()
            for i, (route, _) in enumerate(KINDS[kind]["shots"]):
                ind = route.endswith("@ind"); route = route.replace("@ind", "").format(sym=sym, term=term)
                pg.goto(f"http://127.0.0.1:{port}/app/{route}", wait_until="networkidle")
                pg.wait_for_timeout(2500)
                # 공개 영상에 안 맞는 것 숨기기: 시작 연출·안내 창, 출석 알림, 종목 가격이 담긴 AI 알림 창, 본부장 얼굴(브리핑 카드)
                pg.add_style_tag(content=".tm-splash,#tourAsk,#tmSheet,.pt-flash,.adv-toast,.bcard,#adv-home{display:none!important}")
                if ind:  # 보조지표 켠 모습: 볼린저 + MACD
                    for s in ('[data-ac-ov="bb"]', '[data-ac-sub="macd"]'):
                        el = pg.query_selector(s)
                        if el: el.click(); pg.wait_for_timeout(500)
                    pg.evaluate("document.getElementById('acBox')?.scrollIntoView({block:'start'})")
                    pg.evaluate("window.scrollBy(0,-120)")
                elif route.startswith("#learn/"):  # 그 용어를 펼친 자리로
                    pg.wait_for_timeout(900); pg.evaluate(f"document.getElementById('lr-{term}')?.scrollIntoView({{block:'start'}})"); pg.evaluate("window.scrollBy(0,-90)")
                elif route.startswith("#analysis/"):
                    pg.evaluate("document.getElementById('acBox')?.scrollIntoView({block:'start'})"); pg.evaluate("window.scrollBy(0,-170)")
                pg.wait_for_timeout(800)
                f = tmp / f"s{i}.png"; pg.screenshot(path=str(f)); out.append(f)
            b.close()
    finally:
        srv.shutdown()
    return out


def _bg() -> Image.Image:
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; d.line([(0, y), (W, y)], fill=(int(108 - 40 * t), int(92 - 50 * t), int(231 - 90 * t)))
    return im


def _text_center(d, y, lines, size, fill=WHITE, w="ExtraBold", gap=1.22):
    f = F(w, size)
    for i, t in enumerate(lines):
        d.text((W // 2, y + i * int(size * gap)), t, font=f, fill=fill, anchor="mt")


def _hook(lines: list[str], host: tuple[str, str, str], tag: str = "AI 투자연구소") -> Image.Image:
    hid, hname, hrole = host
    im = _bg(); d = ImageDraw.Draw(im)
    ph = _photo(hid, 560, 700, 60); im.paste(ph[0], ((W - 560) // 2, 860), ph[1])
    tw = d.textlength(tag, font=F("Bold", 44)) / 2 + 50
    d.rounded_rectangle((W // 2 - tw, 150, W // 2 + tw, 230), 40, fill=WHITE)
    d.text((W // 2, 190), tag, font=F("Bold", 44), fill=LAVD, anchor="mm")
    size = 118 if max(len(x) for x in lines) <= 8 else 100
    _text_center(d, 300, lines, size)
    d.rounded_rectangle((W // 2 - 250, 1600, W // 2 + 250, 1690), 45, fill=WHITE)
    d.text((W // 2, 1645), f"{hname} · {hrole} 담당", font=F("Bold", 42), fill=INK, anchor="mm")
    return im


def _phone(shot: Path, cap: str, sec: float) -> list[Image.Image]:
    """앱 화면을 휴대폰 틀 안에서 위→아래로 천천히."""
    s = Image.open(shot).convert("RGB")
    pw = 820; s = s.resize((pw, int(s.height * pw / s.width)))
    ph_h = 1380; top1 = max(0, min(s.height - ph_h, 520))
    base = _bg(); bd = ImageDraw.Draw(base)
    _text_center(bd, 120, [cap], 64)
    x0, y0 = (W - pw) // 2, 330
    shadow = Image.new("RGBA", (pw + 80, ph_h + 80), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((40, 50, pw + 40, ph_h + 40), 60, fill=(20, 10, 60, 120)); shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    base.paste(shadow, (x0 - 40, y0 - 40), shadow)
    mask = Image.new("L", (pw, ph_h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw, ph_h), 54, fill=255)
    out, n = [], int(sec * FPS)
    for k in range(n):
        t = k / max(1, n - 1); e = t * t * (3 - 2 * t)
        top = int(top1 * max(0, (e - 0.15) / 0.85))
        fr = base.copy(); fr.paste(s.crop((0, top, pw, top + ph_h)), (x0, y0), mask); out.append(fr)
    return out


def _wrapw(d, text: str, font, width: int) -> list[str]:
    """띄어쓰기 단위 줄바꿈 (숫자·단어가 중간에 잘리지 않게). 한 단어가 너무 길면 글자 단위."""
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width: cur = t; continue
        if cur: lines.append(cur)
        cur = w
        if d.textlength(w, font=font) > width:
            parts = _wrap(d, w, font, width); lines += parts[:-1]; cur = parts[-1]
    return lines + ([cur] if cur else [])


def _panel(title: str, text: str, foot: str = "", color=INK) -> Image.Image:
    """글 장면: 위에 작은 제목, 가운데 흰 카드에 큰 글씨(카드를 꽉 채우도록 글자 크기 자동, 세로 가운데)."""
    im = _bg(); d = ImageDraw.Draw(im)
    _text_center(d, 200, [title], 64, w="ExtraBold", fill=WHITE)
    box = (70, 360, W - 70, 1520); bw = box[2] - box[0] - 140; bh = box[3] - box[1] - 140
    d.rounded_rectangle(box, 60, fill=WHITE)
    for size in range(104, 50, -4):
        f = F("ExtraBold", size); ls = _wrapw(d, text, f, bw); lh = int(size * 1.42)
        if len(ls) * lh <= bh: break
    y = box[1] + (box[3] - box[1] - len(ls) * lh) // 2
    for ln in ls:
        d.text((W // 2, y), ln, font=f, fill=color, anchor="mt"); y += lh
    if foot: _text_center(d, 1600, [foot], 40, w="Medium", fill=(235, 232, 255))
    return im


def _end(md: str, lines=("남기면 DM으로", "바로 보내 드려요"), sub=("실제 거래소 종가 그대로", "가상 돈으로 하는 연습용 게임")) -> Image.Image:
    im = _bg(); d = ImageDraw.Draw(im)
    _text_center(d, 330, ["댓글에", "'연구소'"], 120)
    _text_center(d, 640, list(lines), 78, w="Bold")
    d.rounded_rectangle((W // 2 - 300, 940, W // 2 + 300, 1040), 50, fill=WHITE)
    d.text((W // 2, 990), "팔로워 선공개", font=F("ExtraBold", 50), fill=LAVD, anchor="mm")
    _text_center(d, 1180, list(sub), 46, w="Medium", fill=(235, 232, 255))
    _text_center(d, 1780, [f"{md} 장 마감 기준 · 투자 권유 아님"], 34, w="Medium", fill=(210, 205, 245))
    return im


def frames_app(shots: list[Path], kind: str, host, md: str) -> tuple[list, Image.Image]:
    """앱 소개: 훅(2.5초) → 앱 화면 3개(각 3.4초) → 마무리(2.3초)."""
    K = KINDS[kind]; hook = _hook(K["hook"], host)
    seq = [hook] * int(2.5 * FPS)
    for (_, cap), shot in zip(K["shots"], shots): seq += _phone(shot, cap, 3.4)
    seq += [_end(md)] * int(2.3 * FPS)
    return seq, hook


def frames_word(shots: list[Path], t: dict, lv: str, n_terms: int, host, md: str) -> tuple[list, Image.Image]:
    """용어: 질문(2.2초) → 한 줄 뜻(3.2) → 읽는 법(3.2) → 오늘 숫자(2.0, 있으면) → 앱 용어 사전(2.4) → 마무리(2.0)."""
    hook = _hook([t["q"]] if len(t["q"]) <= 9 else _split(t["q"]), host, tag="30초 주식 용어")
    seq = [hook] * int(2.2 * FPS)
    seq += [_panel(f"{t['name']} = {t['full']}", t["one"])] * int(3.2 * FPS)
    seq += [_panel("읽는 법", t["how"])] * int((3.2 if lv else 4.2) * FPS)
    if lv: seq += [_panel("오늘 실제 숫자로 보면", lv, "공개 자료 · 참고용", color=LAVD)] * int(2.0 * FPS)
    seq += _phone(shots[0], f"앱 용어 사전 {n_terms}개, 오늘 숫자와 함께", 2.4)
    seq += [_end(md, ("남기면 용어 사전과", "모의투자 게임을 보내 드려요"), ("PER부터 RSI까지 오늘 숫자로", "가상 돈으로 하는 연습용 게임"))] * int(2.0 * FPS)
    return seq, hook


def _split(q: str) -> list[str]:  # 긴 질문을 두 줄로 (띄어쓰기 기준)
    w = q.split(" "); best = min(range(1, len(w)), key=lambda i: abs(len(" ".join(w[:i])) - len(" ".join(w[i:])))) if len(w) > 1 else 1
    return [" ".join(w[:best]), " ".join(w[best:])] if len(w) > 1 else [q]


def _write(seq: list, cover: Image.Image, tmp: Path) -> Path:
    fd = tmp / "f"; fd.mkdir(exist_ok=True); last = None
    for i, im in enumerate(seq):  # 같은 장면은 파일을 복사해 시간 절약
        p = fd / f"{i:04d}.jpg"
        if im is last: shutil.copyfile(fd / f"{i - 1:04d}.jpg", p)
        else: im.save(p, quality=90)
        last = im
    cover.save(tmp / "cover.jpg", quality=90)
    return fd


def build(web: Path, kind: str | None = None) -> dict | None:
    web = Path(web); data = web / "data"
    sc = json.loads((data / "scores.json").read_text(encoding="utf-8"))
    op = data / "outlook.json"; facts = json.loads(op.read_text(encoding="utf-8")).get("facts", {}) if op.exists() else {}
    date = sc["date"]; d = dt.date.fromisoformat(date); md = f"{d.month}월 {d.day}일"
    kind = kind or BY_WEEKDAY.get(d.weekday())
    if not kind: return None
    if kind == "app": kind = APP_KINDS[_week(d) % len(APP_KINDS)]
    sym = EX if EX in sc["stocks"] else next(iter(sc["stocks"]))
    host = host_of(date); hname = host[1]
    josa = "이" if (ord(hname[-1]) - 0xAC00) % 28 else "가"
    G = json.loads((web / "app" / "glossary.json").read_text(encoding="utf-8")); TT = {t["id"]: t for t in G["terms"]}
    term = TT[os.environ.get("REEL_TERM") or WORD_ORDER[_week(d) % len(WORD_ORDER)]] if kind == "word" else None  # REEL_TERM: 시험용
    out = data / "reel"; out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tdir:
        tmp = Path(tdir)
        shots = shoot(web, kind, sym, tmp, term["id"] if term else "")
        if term:
            lv = live(term, sc, facts)
            seq, cover = frames_word(shots, term, lv, len(G["terms"]), host, md)
        else:
            seq, cover = frames_app(shots, kind, host, md)
        fd = _write(seq, cover, tmp)
        music = web / "app" / "bgm" / "main.mp3"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg")]
        if music.exists(): cmd += ["-i", str(music), "-filter_complex", "[1:a]volume=1.6,afade=t=in:d=0.8,afade=t=out:st=14:d=1[a]", "-map", "0:v", "-map", "[a]"]
        cmd += ["-t", "15", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "21", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out / "reel.mp4")]
        subprocess.run(cmd, check=True)
        shutil.copyfile(tmp / "cover.jpg", out / "cover.jpg")
    if term:
        lv_line = f"\n📌 {lv}" if lv else ""
        caption = f"""{term['q']} 30초 주식 용어 📘
{hname}{josa} 쉽게 풀어 드려요 ({md})

✔ {term['name']} ({term['full']}): {term['one']}
✔ 읽는 법: {term['how']}{lv_line}

💬 댓글에 '연구소' 남기면 PER부터 RSI까지 {len(G['terms'])}개 용어를 오늘 숫자로 보는 사전과 모의투자 게임을 DM으로 보내 드려요 (팔로워 선공개)
📌 저장해 두고 헷갈릴 때 다시 보기

※ 공개 자료로 만든 학습용 설명이며 투자 권유가 아닙니다.

#주식공부 #주식용어 #주식초보 #{term['name'].replace(' ', '').replace('/', '')} #재테크 #직장인재테크 #모의투자 #AI투자"""
    else:
        K = KINDS[kind]
        caption = f"""{' '.join(K['hook'])} 🎮
{hname}{josa} 소개하는 AI 투자연구소 ({md})

📌 실제 거래소 종가 그대로
📌 하루 한 번, 퇴근길 5분이면 끝나는 종가 스윙 연습
📌 AI 팀 '알파'와 같은 날·같은 돈으로 수익률 대결

💬 댓글에 '연구소' 남기면 DM으로 보내 드려요 (팔로워 선공개)

※ 가상 돈으로 하는 모의투자 게임이며 투자 권유가 아닙니다.

#주식 #모의투자 #주식게임 #주식공부 #재테크 #직장인재테크 #AI투자 #종가매매"""
    info = {"date": date, "kind": kind, "term": term["id"] if term else None, "host": host[0],
            "video": "reel/reel.mp4", "cover": "reel/cover.jpg", "caption": caption}
    (out / "reel.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


if __name__ == "__main__":
    r = build(Path(sys.argv[1] if len(sys.argv) > 1 else "web"), sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(r, ensure_ascii=False, indent=1) if r else "오늘은 릴스 없는 날 (화·목만)")
