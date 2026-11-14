"""주간 차트 퀴즈 릴스 (1080x1920, 약 17초). 2026-11-05 사용자: "주 1회 퀴즈, 오를까? 내릴까? 훅으로 한 종목의 과거 차트를 보여 주며
댓글 유도, 정답은 다른 게시물 시청 유도하고 그 게시물에 답과 차트 추가"

- 수 12:00 퀴즈 릴스: 실제 '과거' 차트(이름 가림)를 그 지점까지만 그리고 "한 달 뒤 오를까? 내릴까? 댓글로 1·2"
- 목 17:50 장마감 릴스 마지막 앞 장면: 이름 공개 + 가렸던 뒷부분 차트 + 결과 (cards_reel.py 가 quiz.json 을 읽어 붙임)
- 지금 종목이 아니라 지난 시세라서 권유가 아니라 차트 공부용. 힌트는 그날 실제 숫자(RSI·거래량·20일선) 하나.
- 정답 방향은 주마다 섞이게(짝수 주 상승 쪽 우선) 고르고, 한 달 뒤 결과가 ±8~40% 로 분명한 장면만 쓴다.
결과: <web>/data/quiz/quiz.mp4, cover.jpg, quiz.json {date, answer_date, sym, name, cut, up, chg, hint, caption, bars}
실행: python -m ai_trading.data.quiz web [올릴 날짜 YYYY-MM-DD]   (화요일 데이터 실행 때 수요일 날짜로 만들어 둠)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from ai_trading.data.hashtags import line as _htag

AHEAD = 20   # 정답: 20거래일(약 한 달) 뒤
SHOW = 60    # 퀴즈 차트에 보이는 봉 수
QUIZ_TAGS = _htag(["주식", "코스피", "재테크", "증시"], ["차트퀴즈", "투자퀴즈", "차트공부", "캔들차트"])


def rsi(c: list, k: int, n: int = 14) -> float:
    g = l = 0.0
    for i in range(k - n + 1, k + 1):
        d = c[i] - c[i - 1]; g += max(d, 0); l += max(-d, 0)
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def hint_of(st: dict, k: int) -> str:
    """그날 실제 숫자 한 줄 (가장 눈에 띄는 것)."""
    c, v = st["c"], st["v"]
    r = rsi(c, k)
    vr = v[k] / (sorted(v[k - 60:k])[30] or 1)
    ma = sum(c[k - 19:k + 1]) / 20; gap = (c[k] / ma - 1) * 100
    if r <= 30: return f"RSI {r:.0f} · 많이 빠진 구간(30 아래)"
    if r >= 70: return f"RSI {r:.0f} · 많이 오른 구간(70 위)"
    if vr >= 2: return f"마지막 날 거래량이 평소의 {vr:.1f}배"
    return f"주가가 20일 평균선보다 {'+' if gap >= 0 else ''}{gap:.1f}%"


def _period(a: str, b: str) -> str:
    ya, ma, yb, mb = int(a[:4]), int(a[5:7]), int(b[:4]), int(b[5:7])
    return f"{ya}년 {ma}월~{mb}월" if ya == yb else f"{ya}년 {ma}월~{yb}년 {mb}월"


def pick(market: dict, at: str) -> dict | None:
    """올릴 날짜(at)로 정해지는 무작위(같은 날 다시 만들어도 같은 문제). 최근 25거래일은 빼고 '지난' 차트만."""
    dates = market["dates"]; n = len(dates)
    rnd = random.Random(f"quiz-{at}")
    want_up = dt.date.fromisoformat(at).isocalendar()[1] % 2 == 0
    # 거래대금 큰 종목(이름 들으면 아는 회사) 위주
    big = sorted(market["stocks"].values(), key=lambda s: -sum(a * b for a, b in zip(s["c"][-60:], s["v"][-60:])))[:40]
    cands = {True: [], False: []}
    for st in big:
        c = st["c"]
        if len(c) != n: continue
        for k in range(SHOW + 60, n - AHEAD - 25):  # 60일 이평선을 처음부터 그릴 수 있게 앞쪽 여유
            r = c[k + AHEAD] / c[k] - 1
            if 0.10 <= abs(r) <= 0.40: cands[r > 0].append((st, k, r))
    pool = cands[want_up] or cands[not want_up]
    if not pool: return None
    st, k, r = rnd.choice(pool)
    s0 = k - SHOW + 1; s1 = k + AHEAD + 1
    c = st["c"]
    ma = lambda p: [round(sum(c[i - p + 1:i + 1]) / p, 2) for i in range(s0, s1)]
    return {"sym": st["sym"], "name": st["name"], "cut": dates[k], "cut_i": SHOW - 1, "up": r > 0, "chg": round(r * 100, 1),
            "hint": hint_of(st, k), "period": _period(dates[s0], dates[k]),
            "bars": {"d": dates[s0:s1], "o": st["o"][s0:s1], "h": st["h"][s0:s1], "l": st["l"][s0:s1], "c": st["c"][s0:s1],
                     "ma": {"5": ma(5), "20": ma(20), "60": ma(60)}, "rsi": [round(rsi(c, i), 1) for i in range(s0, s1)]}}


# ---------- 차트 그리기 (퀴즈·정답 장면 공통) ----------
def draw_chart(im: Image.Image, Q: dict, box: tuple, upto: float, reveal: float = 0.0, mask: bool = True):
    """box=(x0,y0,x1,y1). upto: 앞 60봉 중 그린 비율(0~1). reveal: 가린 뒤 20봉 중 드러낸 비율. mask: 뒤쪽 '?' 칸."""
    from ai_trading.data.cards_reel import rr, T, RED, BLUE, DIM, FG, YEL
    b = Q["bars"]; N = len(b["c"]); cut = Q["cut_i"]
    x0, y0, x1, y1 = box
    rr(im, (x0 + 4, y0 + 8, x1 + 4, y1 + 8), 36, (20, 30, 60, 18)); rr(im, box, 36, (255, 255, 255, 255))
    MAS = b.get("ma") or {}; RS = b.get("rsi")  # 보조지표 (2026-11-14 사용자: 이평선·RSI가 있어야 예측하는 재미)
    px0, px1, py0 = x0 + 30, x1 - 30, y0 + 70
    ry1 = y1 - 30; ry0 = ry1 - 150 if RS else ry1
    py1 = ry0 - 50 if RS else y1 - 40
    m = N if (reveal > 0 or not mask) else cut + 1  # 퀴즈 땐 보이는 부분으로만 눈금 (뒤쪽 높낮이가 새지 않게)
    vals = b["l"][:m] + b["h"][:m] + [v for line in MAS.values() for v in line[:m]]
    lo, hi = min(vals), max(vals); sp = (hi - lo) or 1
    Y = lambda v: py1 - (v - lo) / sp * (py1 - py0)
    bw = (px1 - px0) / N
    d = ImageDraw.Draw(im, "RGBA")
    for g in range(1, 4):  # 가로 눈금
        yy = py0 + (py1 - py0) * g / 4; d.line([(px0, yy), (px1, yy)], fill=(20, 30, 60, 22), width=2)
    shown = int((cut + 1) * upto) + (int(AHEAD * reveal) if upto >= 1 else 0)
    for i in range(min(shown, m)):
        o, h, l, c = b["o"][i], b["h"][i], b["l"][i], b["c"][i]
        col = RED if c >= o else BLUE
        if i > cut: col = (RED if Q["up"] else BLUE)  # 정답 부분은 결과 색
        cx = px0 + bw * (i + 0.5)
        d.line([(cx, Y(h)), (cx, Y(l))], fill=col + (255,), width=3)
        t, btm = sorted((Y(o), Y(c))); d.rectangle((cx - bw * 0.36, t, cx + bw * 0.36, max(btm, t + 3)), fill=col + (255,))
    vis = min(shown, m)
    MA_COL = {"5": (255, 140, 0), "20": (0, 160, 110), "60": (140, 80, 220)}
    for p, line in MAS.items():  # 이평선
        pts = [(px0 + bw * (i + 0.5), Y(line[i])) for i in range(vis)]
        if len(pts) > 1: d.line(pts, fill=MA_COL.get(p, DIM) + (230,), width=4, joint="curve")
    lx = px0
    for p in MAS:  # 범례
        d.line([(lx, y0 + 38), (lx + 34, y0 + 38)], fill=MA_COL.get(p, DIM) + (255,), width=6)
        T(im, f"{p}일선", lx + 42, y0 + 22, 26, FG, "Bold"); lx += 150
    if RS:  # RSI 칸
        RY = lambda v: ry1 - v / 100 * (ry1 - ry0)
        d.line([(px0, ry0 - 18), (px1, ry0 - 18)], fill=(20, 30, 60, 30), width=2)
        for lv, col in ((70, RED), (30, BLUE)):
            for xx in range(int(px0), int(px1), 24): d.line([(xx, RY(lv)), (min(xx + 12, px1), RY(lv))], fill=col + (150,), width=2)
            T(im, str(lv), px1 - 4, RY(lv), 22, col, "Bold", anchor="rm")
        pts = [(px0 + bw * (i + 0.5), RY(RS[i])) for i in range(vis)]
        if len(pts) > 1: d.line(pts, fill=FG + (255,), width=4, joint="curve")
        T(im, f"RSI(14) {RS[vis - 1]:.0f}" if vis else "RSI(14)", px0, ry0 - 12, 26, DIM, "Bold")
    xc = px0 + bw * (cut + 1)
    if mask and reveal <= 0 and upto >= 1:  # 가린 칸 (가격·RSI 모두)
        rr(im, (int(xc + 6), py0 - 10, px1 + 10, ry1 + 10), 24, (20, 30, 60, 26))
        T(im, "?", (xc + px1) / 2, (py0 + py1) / 2, 180, FG, anchor="mm")
        T(im, "한 달 뒤", (xc + px1) / 2, py1 - 40, 34, DIM, "Bold", anchor="mm")
    if upto >= 1:  # 문제 지점 표시
        d.line([(xc, py0 - 20), (xc, ry1 + 10)], fill=YEL + (255,), width=6)
        cy = Y(b["c"][cut]); d.ellipse((xc - bw * 0.5 - 12, cy - 12, xc - bw * 0.5 + 12, cy + 12), outline=FG + (255,), width=5)


# ---------- 퀴즈 릴스 ----------
SCENES = [3.0, 5.0, 3.2, 3.6, 2.6]


def render(web: Path, at: str) -> dict | None:
    from ai_trading.data.cards_reel import (W, H, FPS, ACC, BLUE, DIM, FG, RED, WHITE, YEL, T, back, bg_at, make_bg, out3, prog, rr)
    web = Path(web); data = web / "data"
    Q = pick(json.loads((data / "market.json").read_text(encoding="utf-8")), at)
    if not Q: print("[퀴즈] 알맞은 과거 장면이 없음 → 건너뜀"); return None
    out = data / "quiz"; out.mkdir(parents=True, exist_ok=True)
    d0 = dt.date.fromisoformat(at); ans = d0 + dt.timedelta(days=7)  # 정답은 다음 주 토요일 퀴즈 릴스
    ans_md = f"{ans.month}월 {ans.day}일"
    BG = make_bg(); CH = (50, 470, 1030, 1330)
    starts = [sum(SCENES[:i]) for i in range(len(SCENES))]; total = sum(SCENES)

    def frame(tt: float) -> Image.Image:
        k = max(i for i in range(len(starts)) if starts[i] <= tt); t = tt - starts[k]
        im = bg_at(BG, tt, 1 if Q["up"] else -1)
        T(im, "AI 투자연구소 · 주간 차트 퀴즈", 60, 60, 36, FG, "Bold")
        if k == 0:  # 훅: 오를까? 내릴까?
            a = prog(t, 0, 0.35); T(im, "오를까?", W // 2, 640, 190, RED, anchor="mm", scale=1.6 - 0.6 * back(a) if a < 1 else 1, alpha=a)
            a = prog(t, 0.45, 0.35); T(im, "내릴까?", W // 2, 900, 190, BLUE, anchor="mm", scale=1.6 - 0.6 * back(a) if a < 1 else 1, alpha=a)
            a = prog(t, 1.1, 0.4); T(im, "실제 있었던 차트, 한 달 뒤는?", W // 2, 1150, 52, FG, "Bold", anchor="mm", alpha=a)
            a = prog(t, 1.5, 0.4); rr(im, (300, 1300, 780, 1400), 50, YEL + (int(255 * a),)); T(im, "3초 안에 골라 보세요", W // 2, 1350, 42, FG, anchor="mm", alpha=a)
            return im
        T(im, "이 종목, 한 달 뒤 오를까? 내릴까?", 60, 200, 56, FG)
        T(im, f"종목 이름 ???  ·  {Q['period']}", 64, 290, 38, DIM, "Medium")
        T(im, "실제 지난 차트 · 이름은 정답 릴스에서", 64, 345, 34, DIM, "Medium")
        if k == 1: draw_chart(im, Q, CH, upto=out3(prog(t, 0, 4.0)))
        else: draw_chart(im, Q, CH, upto=1)
        if k == 2:
            a = prog(t, 0, 0.4); y = 1400 + 200 * (1 - out3(a))
            rr(im, (60, y, 1020, y + 180), 40, (255, 255, 255, int(255 * a)))
            T(im, "힌트", 100, y + 30, 40, ACC, alpha=a); T(im, Q["hint"], 100, y + 95, 46, FG, alpha=a)
        if k == 3:
            for i, (lab, sub, c) in enumerate([("1 오른다", "댓글에 1", RED), ("2 내린다", "댓글에 2", BLUE)]):
                a = prog(t, 0.1 + i * 0.25, 0.4); x0 = 60 + i * 490; s = back(a) if a < 1 else 1 + 0.03 * math.sin(t * 6 + i)
                bw, bh = int(470 * s), int(250 * s); bx, by = x0 + 235 - bw // 2, 1500 - bh // 2
                if a > 0: rr(im, (bx, by, bx + bw, by + bh), 40, c + (int(255 * a),))
                T(im, lab, x0 + 235, 1460, 64, WHITE, anchor="mm", alpha=a)
                T(im, sub, x0 + 235, 1550, 40, WHITE, "Bold", anchor="mm", alpha=a)
            T(im, "댓글로 1 또는 2 남겨 주세요", W // 2, 1720, 50, FG, anchor="mm", alpha=prog(t, 0.8, 0.4))
        if k == 4:
            a = prog(t, 0, 0.4); rr(im, (60, 1400, 1020, 1700), 40, FG + (int(240 * a),))
            T(im, "정답은 다음 주 토요일에", W // 2, 1480, 56, WHITE, anchor="mm", alpha=a)
            T(im, f"{ans_md} 토요일 12시 · 팔로우하고 확인", W // 2, 1590, 44, YEL, "Bold", anchor="mm", alpha=prog(t, 0.3, 0.4))
        T(im, "지난 시세로 만든 차트 공부용 퀴즈 · 투자 권유 아님", W // 2, H - 40, 26, DIM, "Medium", anchor="mb")
        return im

    audio = web / "app" / "bgm" / "main.mp3"
    args = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio.exists(): args += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-af", f"afade=t=in:d=0.4,afade=t=out:st={total - 1.2:.2f}:d=1.2", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    args += ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "quiz.mp4")]
    pr = subprocess.Popen(args, stdin=subprocess.PIPE)
    for fi in range(int(total * FPS)):
        fr = frame(fi / FPS)
        if fi == int(9.5 * FPS): fr.convert("RGB").save(out / "cover.jpg", quality=90)  # 표지: 차트 + 힌트
        pr.stdin.write(fr.convert("RGB").tobytes())
    pr.stdin.close(); pr.wait()
    if pr.returncode: raise SystemExit(f"ffmpeg 실패 {pr.returncode}")
    caption = f"""🧩 주간 차트 퀴즈 | 한 달 뒤, 오를까? 내릴까?
실제 있었던 차트예요 ({Q['period']}, 종목 이름은 정답 릴스에서 공개)

💡 힌트: {Q['hint']}

👇 댓글로 골라 주세요
1 = 오른다 📈
2 = 내린다 📉

정답과 가렸던 차트 뒷부분은 다음 주 토요일 퀴즈 릴스에서 공개해요. 팔로우하고 확인하세요!

※ 지난 시세로 만든 차트 공부용 퀴즈이며 투자 권유가 아닙니다.

{QUIZ_TAGS}"""
    info = {"date": at, "answer_date": ans.isoformat(), **Q, "video": "quiz/quiz.mp4", "cover": "quiz/cover.jpg", "caption": caption,
            "answer_line": f"🧩 어제 퀴즈 정답: {Q['name']} → 한 달 뒤 {'+' if Q['chg'] > 0 else ''}{Q['chg']}% ({'1번 오른다' if Q['up'] else '2번 내린다'})"}
    (out / "quiz.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


def answer_due(web: Path, date: str) -> dict | None:
    """장마감 릴스 날짜(date)에 공개할 퀴즈 (없으면 None)."""
    p = Path(web) / "data" / "quiz" / "quiz.json"
    try:
        q = json.loads(p.read_text(encoding="utf-8"))
        return q if q.get("answer_date") == date else None
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    a = sys.argv[1:]; web = Path(a[0] if a else "web")
    at = a[1] if len(a) > 1 else (dt.date.today() + dt.timedelta(days=1)).isoformat()
    r = render(web, at)
    print(json.dumps({k: v for k, v in (r or {}).items() if k != "bars"}, ensure_ascii=False, indent=1) if r else "퀴즈 없음")
