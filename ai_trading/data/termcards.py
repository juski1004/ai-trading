"""주말(토·일) '용어 정리' 카드뉴스 5장 + 캡션. 2026-10-26 사용자: "용어 정리는 릴스 말고 카드뉴스로 토·일".

- 금요일(또는 금요일이 휴장이면 목요일) 데이터 실행 때 그 주 토·일 것을 미리 만든다 → data/termcards/<날짜>/1..5.png, termcards.json
- 용어는 web/app/glossary.json(앱 용어 사전과 같은 설명), 순서는 ai_trading.reel.WORD_ORDER (토 = 주 번호×2, 일 = 주 번호×2+1)
- 진행자·배경색은 장마감 카드와 같은 그날의 사람, 그 주의 색 (cards.host_of / theme_of)
- '오늘 실제 숫자'는 마지막 거래일(금요일) 종가 기준. 권유 문장 없음
장 구성: 1 표지(질문 + 진행자 사진) · 2 한 줄 뜻 · 3 자세히 · 4 읽는 법 + 실제 숫자 · 5 마무리(댓글 '연구소', 팔로우)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from . import cards as C

W, H, N = C.W, C.H, 5
ROOT = Path(__file__).resolve().parents[2]


def _wrapw(d, text, font, width):
    """띄어쓰기 단위 줄바꿈 (숫자·단어가 중간에 잘리지 않게)."""
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width: cur = t; continue
        if cur: lines.append(cur)
        cur = w
        if d.textlength(w, font=font) > width:
            parts = C._wrap(d, w, font, width); lines += parts[:-1]; cur = parts[-1]
    return lines + ([cur] if cur else [])


def weekend_dates(data_date: str) -> list[str]:
    """데이터 날짜가 목·금이면 그 주 토·일 날짜, 아니면 빈 목록."""
    d = dt.date.fromisoformat(data_date)
    if d.weekday() not in (3, 4): return []
    sat = d + dt.timedelta(5 - d.weekday())
    return [sat.isoformat(), (sat + dt.timedelta(1)).isoformat()]


def term_for(date: str, terms: dict) -> dict:
    from ai_trading.reel import WORD_ORDER  # 릴스와 같은 순서
    d = dt.date.fromisoformat(date)
    i = C.week_of(date) * 2 + (1 if d.weekday() == 6 else 0)
    return terms[WORD_ORDER[i % len(WORD_ORDER)]]


def make(date: str, t: dict, lv: str, base_date: str, n_terms: int, dst: Path) -> dict:
    hid, hname, hrole = C.host_of(date)
    th = C.theme_of(date); PAPER, GRID, ACC, LINE = th["paper"], th["grid"], th["acc"], th["line"]
    F = C._font; INK, MUTED, WHITE, MARK = C.INK, C.MUTED, C.WHITE, C.MARK
    josa = "이" if (ord(hname[-1]) - 0xAC00) % 28 else "가"
    bd = f"{int(base_date[5:7])}월 {int(base_date[8:])}일"
    avatar = C._photo(hid, 96, 96, 48)
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("*.png"): old.unlink()

    def base(n, title=None, label=None):
        im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im)
        for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=GRID)
        for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=GRID)
        d.rounded_rectangle((64, 80, 80, 96), 4, fill=ACC); d.text((96, 88), "AI 투자연구소", font=F("Bold", 34), fill=INK, anchor="lm")
        d.text((W - 60, 90), f"{n}/{N}", font=F("Bold", 32), fill=MUTED, anchor="rm")
        if n not in (1, N):
            d.ellipse((W - 222, 40, W - 118, 144), fill=WHITE); im.paste(avatar[0], (W - 218, 44), avatar[1])
            d.text((W - 170, 160), hname, font=F("Bold", 24), fill=ACC, anchor="mt")
        if label:
            tw = d.textlength(label, font=F("Bold", 34))
            d.rounded_rectangle((70, 190, 70 + tw + 56, 250), 30, fill=INK); d.text((98, 220), label, font=F("Bold", 34), fill=WHITE, anchor="lm")
        if title: d.text((70, 280), title, font=F("ExtraBold", 72), fill=INK)
        d.text((W // 2, H - 60), "주말 용어 정리 · 학습용 설명, 투자 권유 아님", font=F("Medium", 26), fill=MUTED, anchor="mm")
        return im, d

    def body(d, text, top, bottom, size_max=64, size_min=40, color=INK, mark_first=False):
        """글자를 영역에 꽉 차게(크기 자동), 첫 줄은 형광펜."""
        for size in range(size_max, size_min - 1, -2):
            f = F("Bold", size); ls = _wrapw(d, text, f, W - 180); lh = int(size * 1.45)
            if len(ls) * lh <= bottom - top: break
        y = top + max(0, (bottom - top - len(ls) * lh) // 2)  # 세로 가운데
        for i, ln in enumerate(ls):
            if mark_first and i == 0:
                d.rounded_rectangle((86, y + int(size * 0.62), 94 + d.textlength(ln, font=f), y + int(size * 1.12)), 8, fill=MARK)
            d.text((90, y), ln, font=f, fill=color); y += lh
        return y

    # 1. 표지: 질문 + 진행자 사진 크게
    im, d = base(1)
    d.rounded_rectangle((70, 180, 70 + d.textlength("주말 용어 정리", font=F("Bold", 36)) + 56, 244), 32, fill=ACC)
    d.text((98, 212), "주말 용어 정리", font=F("Bold", 36), fill=WHITE, anchor="lm")
    d.text((70, 280), f"{hname}{josa} 알려주는", font=F("Bold", 50), fill=ACC)
    q = t["q"]; fq = F("ExtraBold", 108 if len(q) <= 8 else 92)
    ls = _wrapw(d, q, fq, W - 140); y = 360
    for ln in ls[:2]:
        d.text((66, y), ln, font=fq, fill=INK); y += int(fq.size * 1.2)
    ph = C._photo(hid, 520, 640, 44)
    d.rounded_rectangle((W - 600, 600, W - 60, 1260), 50, fill=WHITE, outline=LINE, width=2); im.paste(ph[0], (W - 590, 610), ph[1])
    d.text((70, 1050), f"{t['name']}", font=F("ExtraBold", 72), fill=ACC)
    d.text((72, 1140), t["full"], font=F("Medium", 34), fill=MUTED)
    d.text((72, 1210), "넘겨 보기 →", font=F("Bold", 34), fill=ACC)
    im.save(dst / "1.png")

    # 2. 한 줄 뜻
    im, d = base(2, None, "한 줄로 말하면")
    d.text((70, 300), t["name"], font=F("ExtraBold", 140 if len(t["name"]) <= 5 else 96), fill=ACC)
    d.text((74, 480), t["full"], font=F("Medium", 38), fill=MUTED)
    C_box = (70, 580, W - 70, 1180); d.rounded_rectangle(C_box, 40, fill=WHITE, outline=LINE, width=2)
    body(d, t["one"], 620, 1150, 96, 44, mark_first=True)
    im.save(dst / "2.png")

    # 3. 자세히
    im, d = base(3, None, "조금 더 자세히")
    d.rounded_rectangle((70, 300, W - 70, 1180), 40, fill=WHITE, outline=LINE, width=2)
    body(d, t["body"], 340, 1150, 88, 40)
    im.save(dst / "3.png")

    # 4. 읽는 법 + 실제 숫자
    im, d = base(4, None, "읽는 법")
    d.rounded_rectangle((70, 300, W - 70, 880 if lv else 1180), 40, fill=WHITE, outline=LINE, width=2)
    body(d, t["how"], 330, 850 if lv else 1150, 80, 38, mark_first=True)
    if lv:
        d.text((76, 930), f"실제 숫자로 보면 ({bd} 종가 기준)", font=F("Bold", 34), fill=MUTED)
        d.rounded_rectangle((70, 990, W - 70, 1180), 40, fill=ACC)
        f = F("ExtraBold", 56)
        for size in (56, 50, 44, 38):
            f = F("ExtraBold", size)
            if d.textlength(lv, font=f) <= W - 200: break
        lsv = _wrapw(d, lv, f, W - 200)
        y = 1085 - (len(lsv) * int(f.size * 1.3)) // 2
        for ln in lsv[:2]:
            d.text((W // 2, y), ln, font=f, fill=WHITE, anchor="mt"); y += int(f.size * 1.3)
    im.save(dst / "4.png")

    # 5. 마무리
    im, d = base(5)
    d.text((70, 200), "용어 사전", font=F("ExtraBold", 80), fill=INK)
    d.text((70, 300), f"PER부터 RSI까지 {n_terms}개", font=F("ExtraBold", 80), fill=ACC)
    d.text((72, 420), "오늘 숫자와 함께 정리해 뒀어요", font=F("Medium", 40), fill=MUTED)
    d.rounded_rectangle((70, 520, W - 70, 760), 40, fill=WHITE, outline=LINE, width=2)
    d.text((W // 2, 590), "팔로우하고 '연구소' 남기면", font=F("Bold", 46), fill=INK, anchor="mt")
    d.text((W // 2, 660), f"무료 {C.cta_app(date)} 드려요", font=F("Bold", 44), fill=ACC, anchor="mt")
    d.rounded_rectangle((70, 830, W - 70, 1240), 40, fill=WHITE, outline=LINE, width=2)
    ph = C._photo(hid, 240, 320, 28); im.paste(ph[0], (100, 875), ph[1])
    d.text((370, 880), f"오늘 진행은 {hname}", font=F("ExtraBold", 44), fill=INK)
    d.text((370, 945), "평일 17:50 장마감 요약", font=F("Medium", 34), fill=MUTED)
    d.text((370, 995), "주말엔 주식 용어 정리", font=F("Medium", 34), fill=MUTED)
    d.rounded_rectangle((370, 1120, 975, 1190), 34, fill=ACC)
    d.text((672, 1155), "저장하고 팔로우하기", font=F("Bold", 34), fill=WHITE, anchor="mm")
    im.save(dst / "5.png")

    lv_line = f"\n📌 실제 숫자: {lv}" if lv else ""
    tag = t["name"].replace(" ", "").replace("/", "").replace("·", "")
    caption = f"""{hname}{josa} 알려주는 주말 용어 정리 | {t['q']}

✔ {t['name']} ({t['full']}): {t['one']}
✔ 자세히: {t['body']}
✔ 읽는 법: {t['how']}{lv_line}

📌 저장해 두고 헷갈릴 때 다시 보기
👉 평일 17시 50분엔 장마감 요약, 주말엔 주식 용어 정리
💬 {C.cta_line(date)}

※ 공개 자료로 만든 학습용 설명이며 투자 권유가 아닙니다.

#주식 #주식투자 #주식공부 #재테크 #주식용어 #주식초보 #{tag} #주말주식공부"""
    rel = dst.name
    return {"date": date, "term": t["id"], "name": t["name"], "host": hid, "hostName": hname,
            "images": [f"termcards/{rel}/{i}.png" for i in range(1, N + 1)], "caption": caption}


def build(out: Path, dates: list[str] | None = None) -> dict | None:
    out = Path(out)
    sc = json.loads((out / "scores.json").read_text(encoding="utf-8"))
    dates = dates or weekend_dates(sc["date"])
    if not dates: return None
    op = out / "outlook.json"; facts = json.loads(op.read_text(encoding="utf-8")).get("facts", {}) if op.exists() else {}
    G = json.loads((ROOT / "web" / "app" / "glossary.json").read_text(encoding="utf-8")); TT = {t["id"]: t for t in G["terms"]}
    from ai_trading.reel import live
    root = out / "termcards"; root.mkdir(parents=True, exist_ok=True)
    items = []
    for date in dates:
        t = term_for(date, TT)
        items.append(make(date, t, live(t, sc, facts), sc["date"], len(G["terms"]), root / date))
    info = {"base": sc["date"], "items": items}
    (root / "termcards.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


if __name__ == "__main__":
    r = build(Path(sys.argv[1] if len(sys.argv) > 1 else "web/data"), sys.argv[2:] or None)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:1500] if r else "주말 용어 카드 만들 날이 아님 (목·금 데이터에서만)")
