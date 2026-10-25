"""인스타 릴스 자동 제작 (화·목·금, 15초 세로 1080x1920).

실제 앱 화면을 찍어(크롬, 휴대폰 크기) 위아래로 천천히 움직이는 장면으로 잇고, 큰 자막·진행 직원 얼굴·잔잔한 배경음을 얹는다.
- 화: '앱 둘러보기'  · 목: '차트와 보조지표'  · 금: 'AI 팀 알파와 대결'
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

from ai_trading.data.cards import FONT, TEAM_IMG, _photo, host_of

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
BY_WEEKDAY = {1: "tour", 3: "chart", 4: "vs"}


def _serve(root: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def shoot(web: Path, kind: str, sym: str, tmp: Path) -> list[Path]:
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
                ind = route.endswith("@ind"); route = route.replace("@ind", "").format(sym=sym)
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


def frames(shots: list[Path], kind: str, host: tuple[str, str, str], md: str, tmp: Path) -> Path:
    """장면: 훅(2.5초) → 앱 화면 3개(각 3.4초, 천천히 이동) → 마무리(2.3초). PNG 연속 이미지로 쓴다."""
    K = KINDS[kind]; hid, hname, hrole = host
    seq = []
    # 1) 훅: 진행 직원 얼굴 + 큰 글씨
    hook = _bg(); d = ImageDraw.Draw(hook)
    ph = _photo(hid, 560, 700, 60); hook.paste(ph[0], ((W - 560) // 2, 860), ph[1])
    d.rounded_rectangle((W // 2 - 230, 150, W // 2 + 230, 230), 40, fill=WHITE)
    d.text((W // 2, 190), "AI 투자연구소", font=F("Bold", 44), fill=LAVD, anchor="mm")
    _text_center(d, 300, K["hook"], 118)
    d.rounded_rectangle((W // 2 - 250, 1600, W // 2 + 250, 1690), 45, fill=WHITE)
    d.text((W // 2, 1645), f"{hname} · {hrole} 담당", font=F("Bold", 42), fill=INK, anchor="mm")
    seq += [hook] * int(2.5 * FPS)
    # 2) 앱 화면: 휴대폰 틀 안에서 위→아래로 천천히
    for (route, cap), shot in zip(K["shots"], shots):
        s = Image.open(shot).convert("RGB")
        pw = 820; s = s.resize((pw, int(s.height * pw / s.width)))
        ph_h = 1380; top0 = 0; top1 = max(0, min(s.height - ph_h, 520))
        n = int(3.4 * FPS)
        base = _bg(); bd = ImageDraw.Draw(base)
        _text_center(bd, 120, [cap], 64)
        x0, y0 = (W - pw) // 2, 330
        shadow = Image.new("RGBA", (pw + 80, ph_h + 80), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((40, 50, pw + 40, ph_h + 40), 60, fill=(20, 10, 60, 120)); shadow = shadow.filter(ImageFilter.GaussianBlur(24))
        base.paste(shadow, (x0 - 40, y0 - 40), shadow)
        mask = Image.new("L", (pw, ph_h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw, ph_h), 54, fill=255)
        for k in range(n):
            t = k / max(1, n - 1); e = t * t * (3 - 2 * t)
            top = int(top0 + (top1 - top0) * max(0, (e - 0.15) / 0.85))
            fr = base.copy(); fr.paste(s.crop((0, top, pw, top + ph_h)), (x0, y0), mask)
            seq.append(fr)
    # 3) 마무리: 댓글 '연구소' → DM
    end = _bg(); d = ImageDraw.Draw(end)
    _text_center(d, 330, ["댓글에", "'연구소'"], 120)
    _text_center(d, 640, ["남기면 DM으로", "바로 보내 드려요"], 78, w="Bold")
    d.rounded_rectangle((W // 2 - 300, 940, W // 2 + 300, 1040), 50, fill=WHITE)
    d.text((W // 2, 990), "팔로워 선공개", font=F("ExtraBold", 50), fill=LAVD, anchor="mm")
    _text_center(d, 1180, ["실제 거래소 종가 그대로", "가상 돈으로 하는 연습용 게임"], 46, w="Medium", fill=(235, 232, 255))
    _text_center(d, 1780, [f"{md} 장 마감 기준 · 투자 권유 아님"], 34, w="Medium", fill=(210, 205, 245))
    seq += [end] * int(2.3 * FPS)
    fd = tmp / "f"; fd.mkdir(exist_ok=True)
    last = None
    for i, im in enumerate(seq):  # 같은 장면은 파일을 복사해 시간 절약
        p = fd / f"{i:04d}.jpg"
        if im is last: shutil.copyfile(fd / f"{i - 1:04d}.jpg", p)
        else: im.save(p, quality=90)
        last = im
    hook.save(tmp / "cover.jpg", quality=90)
    return fd


def build(web: Path, kind: str | None = None) -> dict | None:
    web = Path(web); data = web / "data"
    sc = json.loads((data / "scores.json").read_text(encoding="utf-8"))
    date = sc["date"]; d = dt.date.fromisoformat(date); md = f"{d.month}월 {d.day}일"
    kind = kind or BY_WEEKDAY.get(d.weekday())
    if not kind: return None
    ranked = sorted(sc["stocks"].items(), key=lambda x: -x[1].get("cap", 0) if isinstance(x[1].get("cap"), (int, float)) else 0)
    sym = "005930.KS" if "005930.KS" in sc["stocks"] else ranked[0][0]
    host = host_of(date)
    out = data / "reel"; out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        shots = shoot(web, kind, sym, tmp)
        fd = frames(shots, kind, host, md, tmp)
        music = web / "app" / "bgm" / "main.mp3"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg")]
        if music.exists(): cmd += ["-i", str(music), "-filter_complex", "[1:a]volume=1.6,afade=t=in:d=0.8,afade=t=out:st=14:d=1[a]", "-map", "0:v", "-map", "[a]"]
        cmd += ["-t", "15", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "21", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out / "reel.mp4")]
        subprocess.run(cmd, check=True)
        shutil.copyfile(tmp / "cover.jpg", out / "cover.jpg")
    K = KINDS[kind]; hname = host[1]
    caption = f"""{' '.join(K['hook'])} 🎮
{hname}가 소개하는 AI 투자연구소 ({md})

📌 실제 거래소 종가 그대로
📌 하루 한 번, 퇴근길 5분이면 끝나는 종가 스윙 연습
📌 AI 팀 '알파'와 같은 날·같은 돈으로 수익률 대결

💬 댓글에 '연구소' 남기면 DM으로 보내 드려요 (팔로워 선공개)

※ 가상 돈으로 하는 모의투자 게임이며 투자 권유가 아닙니다.

#주식 #모의투자 #주식게임 #주식공부 #재테크 #직장인재테크 #AI투자 #종가매매"""
    if (ord(hname[-1]) - 0xAC00) % 28: caption = caption.replace(f"{hname}가 소개", f"{hname}이 소개")
    info = {"date": date, "kind": kind, "host": host[0], "video": "reel/reel.mp4", "cover": "reel/cover.jpg", "caption": caption}
    (out / "reel.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


if __name__ == "__main__":
    r = build(Path(sys.argv[1] if len(sys.argv) > 1 else "web"), sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(r, ensure_ascii=False, indent=1) if r else "오늘은 릴스 없는 날 (화·목·금만)")
