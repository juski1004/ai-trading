"""인스타 릴스 자동 제작 (주 1개: 금요일 앱 광고, 15초 세로 1080x1920). 2026-10-26 사용자: "용어 정리는 릴스 말고 카드뉴스로 토·일, 광고 릴스는 주 1회 금"
금 앱 광고(주마다 앱 둘러보기 → 차트·보조지표 → 알파와 대결). 용어 릴스(word)는 수동 실행용으로만 남김 — 주말 용어는 data/termcards.py 카드뉴스

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


from ai_trading import motion as M
from ai_trading.data import termcards as TT
from ai_trading.data.cards import cta_line, host_of, theme_of
from ai_trading.data.hashtags import line as _htag

# 앱 소개 릴스 해시태그: 큰 4 + 작은 4, 서로 겹치지 않게 (2026-11-01)
APP_TAGS = _htag(["주식", "코스피", "재테크", "증시"], ["모의투자", "투자게임", "초보투자", "AI투자연구소"])

FPS = M.FPS

# 요일별 이야기 (화=1, 목=3, 금=4)
KINDS = {
    "tour": {"hook": ["퇴근길 5분,", "종가로만 하는", "투자 게임"],
             "shots": [("#home", "오늘 장마감을 AI 직원들이 정리"), ("#analysis", "대형주를 점수로 한눈에"), ("#game", "가상 돈으로 하루 한 번 종가 주문")]},
    # 2026-11-17 사용자: 홍보 릴스는 기능별 특징(AI 종목분석기 · AI 투자대결 · AI 브리핑)으로 주마다 돌아가며
    "analyzer": {"hook": ["감으로 고르지 말고", "1만 번 먼저", "돌려 보세요"],  # 훅 공식 2 (멈춰, 대신 이렇게)
                 "shots": [("#analysis", "대형주를 AI 점수로 한눈에"), ("#analysis/{sym}", "사기 전에 1만 번 시뮬레이션", ".sim-card"),
                           ("#analysis/{sym}@ind", "MACD·RSI 보조지표까지 한 번에")],
                 "points": ["대형주를 AI 점수로 한눈에", "사기 전에 1만 번 돌려 보는 시뮬레이션", "MACD·RSI 보조지표까지 한 번에"]},
    "brief": {"hook": ["장마감 정리 30분", "AI가 하면 1분", "이유까지 한 줄로"],  # 훅 공식 5 (오래 걸리던 일 → 짧게)
              "shots": [("#home", "매일 장마감 AI 브리핑", "h2:마감 현황"), ("#analysis", "내일 체크할 대형주 점수"), ("#learn", "모르는 말은 용어 사전")],
              "points": ["매일 장마감 AI 브리핑", "오른 이유·내린 이유를 한 줄로", "초보도 읽는 용어 사전"]},
    "chart": {"hook": ["차트 보는 법,", "보조지표까지", "손가락으로"],
              "shots": [("#analysis/{sym}", "일·주·월봉, 두 손가락 확대"), ("#analysis/{sym}@ind", "MACD·RSI·볼린저 한 번에"), ("#home", "매일 17:50 장마감 정리")]},
    "vs": {"hook": ["나 vs AI", "같은 돈 1,000만 원", "한 달 뒤 누가 이길까"],  # 훅 공식 17 (A 대 B)
           "shots": [("#vs", "같은 날, 같은 돈으로 시작"), ("#vs", "월간 시즌 랭킹", "#vsRank"), ("#game", "하루 한 번, 종가로 주문")],
           "points": ["AI 팀 '알파'와 같은 날·같은 돈으로 수익률 대결", "월간 시즌 랭킹", "하루 한 번 종가로 주문"]},
}
KINDS["word"] = {"hook": [], "shots": [("#learn/{term}", "용어 사전")]}
# 앱 공개 홍보 (2026-10-30 사용자: "원래 하려던 것에 좋은 점 추가") — 수동 실행용: python -m ai_trading.reel web promo
# shots = (화면 주소, 자막, 맞출 자리) · 기능 하나에 2초
KINDS["promo"] = {"hook": ["드디어", "공개합니다"],
                  "reason": "주식 처음이라 무섭다는 분들이 많아서, 실전 데이터로 연습하는 모의투자 앱을 열었어요",
                  "sticker": "팔로워 한정",
                  "shots": [("#home", "홈 · 오늘 장마감 한눈에", "h2:마감 현황"),
                            ("#home", "바닥 반등 신호", ".rb-card"),
                            ("#analysis/{sym}", "사기 전에 1만 번 돌려 보기", ".sim-card"),
                            ("#vs", "AI 팀과 수익률 대결", ""),
                            ("#vs", "시즌 랭킹", "#vsRank")]}
BY_WEEKDAY = {4: "app"}  # 금요일 데이터 실행 때 만들어 둠 (올리는 건 토요일, 2026-11-01 사용자: 평일 장마감 릴스·토 앱 소개·일 용어 릴스)
KINDS["study"] = {"hook": ["주식 책 안 사도 돼요", "용어 22개면", "차트가 읽혀요"],  # 훅 공식 20 (그거 없어도 돼요)
                  "shots": [("#learn", "주식 용어 사전, 쉬운 말로"), ("#analysis/{sym}@ind", "배운 지표를 차트에서 바로"), ("#game", "가상 돈으로 바로 연습")],
                  "points": ["초보도 읽는 주식 용어 사전", "배운 보조지표를 실제 차트에서 바로 확인", "가상 돈으로 하루 한 번 연습"]}
KINDS["signal"] = {"hook": ["아무도 안 알려 주는", "세력 매집의 흔적", "거래량에 남아요"],  # 훅 공식 3 (아무도 말 안 하는 것)
                   "shots": [("#analysis/{sym}", "매집 흔적까지 AI 종합 판단", "h2:AI 종합 판단"), ("#home", "바닥 반등·매집 신호 매일 정리", "h2:마감 현황"),
                             ("#analysis/{sym}@ind", "거래량·보조지표로 직접 확인")],
                   "points": ["기관·외국인 매집 흔적을 AI가 정리", "바닥 반등 신호 매일 확인", "거래량·보조지표로 직접 확인"]}
# 2026-11-17 사용자: 평일 홍보 2회(화·목) — 기능 5개를 돌아가며 (AI 종목분석기 · AI 투자대결 · AI 브리핑 · 용어 공부 · 세력 매집 신호)
APP_KINDS = ["analyzer", "vs", "brief", "study", "signal"]
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
        if k == "VIX": return f"VIX {facts['VIX']} ({d})"
        if k == "미국10년물": return f"미국 10년 금리 {facts['미국10년물']}% ({d})"
        if k == "usdkrw": return f"원/달러 {num(sc['market']['usdkrw']['v'], 1)}원 ({d})"
        if k == "WTI_20일%": return f"WTI 최근 한 달 {sgn(facts['WTI_20일%'])}% ({d})"
        if k == "frg":
            m = facts["오늘_시장수급_억원"]["KOSPI"]; return f"외국인 코스피 {sgn(m['frg'])}억 · 기관 {sgn(m['org'])}억 ({d})"
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
    seed = {"aiLab.consent.v1": "2026-10-25", "aiLab.team.v1": json.dumps({"dir": "theo", "staff": ["joy", "egen", "oscar", "teto", "ray", "puppy"]}),
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
            for i, sh in enumerate(KINDS[kind]["shots"]):
                route, focus = sh[0], (sh[2] if len(sh) > 2 else "")
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
                elif focus:  # 그 기능이 보이는 자리로 (1만 번 돌려 보기는 눌러서 그래프까지)
                    if focus == ".sim-card":
                        el = pg.query_selector("[data-simgo]")
                        if el: el.click(); pg.wait_for_timeout(1800)
                    if focus.startswith("h2:"):  # 제목 글자로 찾는 자리
                        pg.evaluate("t=>[...document.querySelectorAll('h2')].find(x=>x.textContent.trim().startsWith(t))?.scrollIntoView({block:'start'})", focus[3:])
                    else:
                        pg.evaluate("s=>document.querySelector(s)?.scrollIntoView({block:'start'})", focus)
                    pg.evaluate("window.scrollBy(0,-90)")
                elif route.startswith("#learn/"):  # 그 용어를 펼친 자리로
                    pg.wait_for_timeout(900); pg.evaluate(f"document.getElementById('lr-{term}')?.scrollIntoView({{block:'start'}})"); pg.evaluate("window.scrollBy(0,-90)")
                elif route.startswith("#analysis/"):
                    pg.evaluate("document.getElementById('acBox')?.scrollIntoView({block:'start'})"); pg.evaluate("window.scrollBy(0,-170)")
                elif kind == "promo":  # 홍보 영상: 맨 위부터 (앞 화면의 스크롤이 남지 않게)
                    pg.evaluate("window.scrollTo(0,0)")
                pg.wait_for_timeout(800)
                f = tmp / f"s{i}.png"; pg.screenshot(path=str(f)); out.append(f)
            b.close()
    finally:
        srv.shutdown()
    return out


def make_app(R: "M.Reel", shots: list[Path], kind: str, host, md: str):
    """앱 소개: 훅(2.4초) → 앱 화면 3개(각 3.4초, 좌우 번갈아 날아옴) → 마무리(2.4초)."""
    K = KINDS[kind]
    M.hook(R, K["hook"], host, "AI 투자연구소")
    for i, (sh, shot) in enumerate(zip(K["shots"], shots)):
        cap = sh[1]
        M.phone_scene(R, shot, cap, 3.4, side=1 if i % 2 == 0 else -1)
    M.end_scene(R, md=md, sec=2.4)


def make_promo(R: "M.Reel", shots: list[Path], kind: str, host):
    """앱 공개 홍보: 훅(2.6초) → 기능 5개(각 2초, 왼쪽·오른쪽 번갈아) → 팔로우 안내(2.4초). 구석 스티커는 처음부터 끝까지."""
    K = KINDS[kind]
    R.overlay = M.sticker(K["sticker"])
    M.promo_hook(R, K["hook"], K["reason"], host, "AI 투자연구소")
    for i, ((_, cap, _f), shot) in enumerate(zip(K["shots"], shots)):
        M.feature_scene(R, shot, cap, f"{i + 1}/{len(shots)}", 2.0, side=1 if i % 2 == 0 else -1)
    M.promo_end(R, 2.4)


def make_word(R: "M.Reel", shots: list[Path], t: dict, lv: str, n_terms: int, host, md: str):
    """용어: 질문(2.2) → 한 줄 뜻(3.2) → 읽는 법(3.2) → 오늘 숫자(2.0) → 앱 사전(2.4) → 마무리(2.0)."""
    M.hook(R, M.split_q(t["q"]), host, "30초 주식 용어", sec=2.2)
    M.lines_scene(R, t["full"], t["one"], 3.2, big=t["name"] if len(t["name"]) <= 6 else "", avatar=host[0])
    M.lines_scene(R, "읽는 법", t["how"], 3.2 if lv else 4.2)
    if lv: M.number_scene(R, "오늘 실제 숫자로 보면", lv, 2.0)
    M.phone_scene(R, shots[0], f"앱 용어 사전 {n_terms}개, 오늘 숫자와 함께", 2.4, side=0)
    M.end_scene(R, ("남기면 용어 사전과", "모의투자 게임을 보내 드려요"), ("PER부터 RSI까지 오늘 숫자로", "가상 돈으로 하는 연습용 게임"), md=md, sec=2.0)


def build(web: Path, kind: str | None = None, at: str | None = None, out: Path | None = None) -> dict | None:
    """at: 미리 만들 때 올릴 날짜(그 주 진행자·색·종류). 화면은 지금 데이터라 영상 끝 '장 마감 기준' 날짜는 빼고 만든다.
    out: 결과 폴더(기본 web/data/reel)."""
    web = Path(web); data = web / "data"
    sc = json.loads((data / "scores.json").read_text(encoding="utf-8"))
    op = data / "outlook.json"; facts = json.loads(op.read_text(encoding="utf-8")).get("facts", {}) if op.exists() else {}
    date = at or sc["date"]; d = dt.date.fromisoformat(date); md = f"{d.month}월 {d.day}일"
    end_md = "" if at else md
    kind = kind or BY_WEEKDAY.get(d.weekday())
    if not kind: return None
    if kind == "app": kind = APP_KINDS[(_week(d) * 2 + (1 if d.weekday() >= 3 else 0)) % len(APP_KINDS)]  # 화·목 홍보: 차례로 돌아가며
    sym = EX if EX in sc["stocks"] else next(iter(sc["stocks"]))
    host = host_of(date); hname = host[1]
    M.set_theme(theme_of(date))  # 카드뉴스와 같은 그 주의 색
    josa = "이" if (ord(hname[-1]) - 0xAC00) % 28 else "가"
    G = json.loads((web / "app" / "glossary.json").read_text(encoding="utf-8")); TERMS = {t["id"]: t for t in G["terms"]}  # TT(termcards)와 이름 겹치지 않게
    term = TERMS[os.environ.get("REEL_TERM") or WORD_ORDER[(_week(d) * 2 + (1 if d.weekday() == 3 else 0)) % len(WORD_ORDER)]] if kind == "word" else None  # REEL_TERM: 시험용
    out = Path(out) if out else data / "reel"; out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tdir:
        tmp = Path(tdir)
        shots = shoot(web, kind, sym, tmp, term["id"] if term else "")
        fd = tmp / "f"; R = M.Reel(fd)
        if term:
            lv = live(term, sc, facts)
            make_word(R, shots, term, lv, len(G["terms"]), host, end_md)
        elif kind == "promo":
            make_promo(R, shots, kind, host)
        else:
            make_app(R, shots, kind, host, end_md)
        R.cover.save(tmp / "cover.jpg", quality=90)
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

💬 {cta_line(date)}
📌 저장해 두고 헷갈릴 때 다시 보기

※ 공개 자료로 만든 학습용 설명이며 투자 권유가 아닙니다.

{TT.term_tags(term['name'], term.get('full', ''))}"""
    elif kind == "promo":
        caption = f"""드디어 공개합니다 🎮
{hname}{josa} 소개하는 AI 투자연구소 ({md})

{KINDS[kind]['reason']}.

📌 홈 · 바닥 반등 신호 · 사기 전에 1만 번 돌려 보기 · AI 대결 · 랭킹

💬 {cta_line(date)}

※ 가상 돈으로 하는 모의투자 게임이며 신호는 참고용입니다. 투자 권유가 아닙니다.

{APP_TAGS}"""
    else:
        K = KINDS[kind]
        caption = f"""{' '.join(K['hook'])} 🎮
{hname}{josa} 소개하는 AI 투자연구소 ({md})

{chr(10).join("📌 " + p for p in K.get("points") or ["실제 거래소 종가 그대로", "하루 한 번, 퇴근길 5분이면 끝나는 종가 스윙 연습", "AI 팀 '알파'와 같은 날·같은 돈으로 수익률 대결"])}

💬 {cta_line(date)}

※ 가상 돈으로 하는 모의투자 게임이며 투자 권유가 아닙니다.

{APP_TAGS}"""
    info = {"date": date, "kind": kind, "term": term["id"] if term else None, "host": host[0],
            "video": f"{out.name}/reel.mp4", "cover": f"{out.name}/cover.jpg", "caption": caption}
    (out / "reel.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


if __name__ == "__main__":
    # usage: python -m ai_trading.reel web [kind] [at YYYY-MM-DD] [out 폴더]
    a = sys.argv[1:]; web = Path(a[0] if a else "web")
    r = build(web, a[1] if len(a) > 1 and a[1] != "-" else None, a[2] if len(a) > 2 else None, Path(a[3]) if len(a) > 3 else None)
    print(json.dumps(r, ensure_ascii=False, indent=1) if r else "오늘은 릴스 없는 날 (금요일만)")
