"""인스타 '오늘의 장 마감' 카드뉴스 (세로 1080x1350, 5장) + 캡션.

- 진행자: 직원 6명이 하루씩 돌아가며 맡는다 (본부장은 나오지 않음). 거래일 기준으로 다음 사람.
- 숫자는 모두 scores/outlook(facts)/why 데이터에서 그대로 가져온다. AI가 쓴 문장은 숫자를 틀릴 수 있어 쓰지 않는다.
- 결과: <out>/cards/1.png … 5.png, caption.txt, cards.json (사이트에 함께 올라가 공개 주소가 생김)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).parent / "fonts"
TEAM_IMG = Path(__file__).resolve().parents[2] / "web" / "img" / "team"
W, H = 1080, 1350
# 2026-10-25 사용자: 보라 배경 빼고 릴스와 같은 디자인 (밝은 모눈 종이 + 검정 글씨 + 파랑 포인트 + 노란 형광펜)
INK, MUTED, LAV, LAVD, UP, DOWN = (20, 22, 30), (112, 116, 128), (234, 233, 228), (38, 99, 235), (226, 72, 107), (61, 111, 230)
PAPER, GRID, MARK, LINE = (246, 245, 241), (236, 235, 230), (255, 224, 102), (226, 224, 218)
WHITE = (255, 255, 255)

# 진행자: 직원 9명 + 본부장 2명 = 11명이 하루씩 돌아가며 (여·남 번갈아). 2026-10-30 사용자 지시: 같은 사람 5일은 지겨움 → 매일 한 명씩
HOSTS = [
    ("joy", "윤시아", "시장 흐름"),
    ("egen", "윤하진", "차트 분석"),
    ("oscar", "서하린", "수급·뉴스"),
    ("teto", "강태오", "리스크 점검"),
    ("ray", "차유나", "차트 분석"),
    ("puppy", "서은찬", "수급·뉴스·실적"),
    ("miles", "민채원", "진입 계획"),
    ("seunghyun", "백승현", "본부장"),
    ("nova", "한예린", "큰 흐름·금리"),
    ("theo", "정서연", "본부장"),
    ("lloyd", "강도윤", "리스크 점검"),
]
EPOCH = dt.date(2026, 10, 26)  # 월요일, 이날 윤시아부터 하루에 한 명씩

# 배경 색: 한 주마다 바뀜 (보라는 쓰지 않음). paper=바탕, grid=모눈, acc=포인트 색, line=카드 테두리
THEMES = [
    {"name": "미색", "paper": (246, 245, 241), "grid": (236, 235, 230), "acc": (38, 99, 235), "line": (226, 224, 218)},
    {"name": "민트", "paper": (238, 246, 242), "grid": (226, 238, 232), "acc": (13, 128, 102), "line": (214, 230, 222)},
    {"name": "하늘", "paper": (237, 243, 250), "grid": (225, 233, 243), "acc": (28, 78, 186), "line": (212, 223, 238)},
    {"name": "살구", "paper": (251, 242, 235), "grid": (243, 230, 220), "acc": (194, 94, 28), "line": (236, 220, 206)},
    {"name": "레몬", "paper": (250, 248, 230), "grid": (240, 237, 214), "acc": (36, 112, 72), "line": (232, 228, 200)},
    {"name": "회색", "paper": (242, 243, 245), "grid": (231, 232, 236), "acc": (20, 22, 30), "line": (220, 222, 228)},
]


def week_of(date: str) -> int:
    """EPOCH 주를 0으로 한 주 번호 (월~일이 같은 주)."""
    d = dt.date.fromisoformat(date)
    return (d - EPOCH).days // 7


def host_of(date: str, k: int = 0) -> tuple[str, str, str]:
    """그날의 진행자 (매일 다음 사람, 주말 용어 카드도 이어서). k=1 이면 다음 날 진행자."""
    d = dt.date.fromisoformat(date)
    return HOSTS[((d - EPOCH).days + k) % len(HOSTS)]


def theme_of(date: str) -> dict:
    return THEMES[week_of(date) % len(THEMES)]


def _font(w: str, s: int):
    return ImageFont.truetype(str(FONT / f"Pretendard-{w}.otf"), s)


def _clean(t: str) -> str:  # 글꼴에 없는 기호(이모지·한자 등) 빼기
    return "".join(ch for ch in t if ("가" <= ch <= "힣") or (ch.isascii() and ch.isprintable()) or ch in "·‘’“”…")


def _wrap(d, text, font, width):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) > width:
            lines.append(cur); cur = ch
        else:
            cur += ch
    return lines + ([cur] if cur else [])


def _photo(hid: str, w: int, h: int, r: int) -> tuple[Image.Image, Image.Image]:
    ph = Image.open(TEAM_IMG / f"{hid}.jpg").convert("RGB")
    sw, sh = ph.size  # 비율 유지하며 채우기 (얼굴이 위쪽이라 위 기준으로 자름)
    s = max(w / sw, h / sh); ph = ph.resize((round(sw * s), round(sh * s)), Image.LANCZOS)
    x = (ph.width - w) // 2; ph = ph.crop((x, 0, x + w, h))
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w, h), r, fill=255)
    return ph, m


def build(out: Path) -> dict:
    global PAPER, GRID, LAVD, LINE
    out = Path(out); dst = out / "cards"; dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("*.png"): old.unlink()  # 장 수가 바뀌어도 옛 장이 남지 않게
    sc = json.loads((out / "scores.json").read_text(encoding="utf-8"))
    o = json.loads((out / "outlook.json").read_text(encoding="utf-8"))
    whyp = out / "why.json"; why = json.loads(whyp.read_text(encoding="utf-8")) if whyp.exists() else {}
    fx = o["facts"]; date = sc["date"]; md = f"{int(date[5:7])}월 {int(date[8:])}일"
    hid, hname, hrole = host_of(date); _, nname, _ = host_of(date, 1)
    # 2026-10-29 사용자: 이름은 성 빼고 "시아가 전해주는" 식으로, "이번 주 진행은 누구" 같은 소개는 빼기
    gname = hname[1:] if len(hname) == 3 else hname
    gsub = gname + ("이가" if (ord(gname[-1]) - 0xAC00) % 28 else "가")  # 시아가 / 하진이가
    th = theme_of(date); PAPER, GRID, LAVD, LINE = th["paper"], th["grid"], th["acc"], th["line"]  # 이번 주 색
    F = _font
    pct = lambda x: f"{'+' if x > 0 else ''}{x:.2f}%"
    col = lambda x: UP if x > 0 else DOWN if x < 0 else MUTED
    eok = lambda x: f"{'+' if x > 0 else ''}{x:,.0f}억"
    avatar = _photo(hid, 96, 96, 48)

    N = 5  # 2026-10-25: 6장 → 5장 (지수 흐름 장을 빼고 표지·체크 포인트에 나눠 담음)

    def base(n, title, sub=None):
        im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im)
        for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=GRID)  # 아주 옅은 모눈 (차트 종이 느낌)
        for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=GRID)
        d.rounded_rectangle((64, 80, 80, 96), 4, fill=LAVD); d.text((96, 88), "AI 투자연구소", font=F("Bold", 34), fill=INK, anchor="lm")
        d.text((W - 60, 90), f"{n}/{N}", font=F("Bold", 32), fill=MUTED, anchor="rm")
        if n not in (1, N):  # 오늘 진행자 얼굴 (작게)
            d.ellipse((W - 222, 40, W - 118, 144), fill=WHITE); im.paste(avatar[0], (W - 218, 44), avatar[1])
            d.text((W - 170, 160), gname, font=F("Bold", 24), fill=LAVD, anchor="mt")
        if title: d.text((70, 190), title, font=F("ExtraBold", 72), fill=INK)
        if sub: d.text((72, 290), sub, font=F("Medium", 36), fill=MUTED)
        d.text((W // 2, H - 60), f"{md} 장 마감 기준 · 참고용, 투자 권유 아님", font=F("Medium", 26), fill=MUTED, anchor="mm")
        return im, d

    def card(d, box, r=40, fill=WHITE):
        d.rounded_rectangle(box, r, fill=fill, outline=LINE, width=2)

    k, q = sc["market"]["kospi"], sc["market"]["kosdaq"]
    S = sc["stocks"]; ranked = sorted(S.items(), key=lambda x: -x[1]["chg"])
    WY = why.get("sym", {}) if why.get("date") == date else {}
    mf = fx["오늘_시장수급_억원"]
    up = sum(1 for s in S.values() if s["chg"] > 0); dn = sum(1 for s in S.values() if s["chg"] < 0)

    # 1. 표지 (2026-10-29 사용자: 사진 전체 화면 + 위아래 큰 글씨 + 넘기기 유도)
    big = max(S.values(), key=lambda x: abs(x["chg"]))
    from PIL import ImageFilter
    ph = Image.open(TEAM_IMG / f"{hid}.jpg").convert("RGB")
    ph = ph.resize((W, round(ph.height * W / ph.width)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 80, 2))
    im = ph.crop((0, 40, W, 40 + H)) if ph.height >= H + 40 else ph.resize((W, H), Image.LANCZOS)
    shade = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(shade)
    for y in range(H):  # 위·아래만 어둡게 (얼굴은 밝게)
        t = max(0, 1 - y / 520) if y < 520 else max(0, (y - 760) / (H - 760))
        sd.line([(0, y), (W, y)], fill=int(235 * min(1, t) ** 1.2))
    im = Image.composite(Image.new("RGB", (W, H), (12, 14, 22)), im, shade); d = ImageDraw.Draw(im)
    d.text((60, 70), f"AI 투자연구소 · {md} 장마감", font=F("Bold", 36), fill=WHITE, anchor="lm")
    d.rounded_rectangle((W - 150, 48, W - 50, 94), 23, fill=(0, 0, 0)); d.text((W - 100, 71), f"1/{N}", font=F("Bold", 28), fill=WHITE, anchor="mm")
    d.text((58, 130), f"{big['name']} {pct(big['chg'])}", font=F("ExtraBold", 92), fill=(255, 214, 10))
    d.text((58, 245), "왜 올랐을까?" if big["chg"] > 0 else "왜 빠졌을까?", font=F("ExtraBold", 104), fill=WHITE)
    d.text((60, 900), f"{gsub} 전해주는 오늘 장마감", font=F("Bold", 44), fill=WHITE)
    for i, (lab, x) in enumerate([("코스피", k), ("코스닥", q)]):
        x0 = 60 + i * 500
        d.text((x0, 975), lab, font=F("Bold", 40), fill=(220, 222, 232))
        d.text((x0, 1025), pct(x["chg"]), font=F("ExtraBold", 96), fill=(255, 120, 140) if x["chg"] > 0 else (120, 170, 255) if x["chg"] < 0 else WHITE)
    d.rounded_rectangle((60, 1175, W - 60, 1275), 50, fill=(255, 214, 10))
    d.text((W // 2, 1225), "넘겨서 이유 보기  →", font=F("ExtraBold", 48), fill=(20, 22, 30), anchor="mm")
    d.text((W // 2, H - 30), f"{md} 장 마감 기준 · 참고용, 투자 권유 아님", font=F("Medium", 24), fill=(200, 202, 212), anchor="mm")
    im.save(dst / "1.png")

    # 2·3. 많이 오른 / 내린 종목
    def movers(n, title, items):
        im, d = base(n, title, "이유는 그날 뉴스·공시에서 찾았어요")
        f30 = F("Medium", 30)
        for i, (sym, s) in enumerate(items):
            y0 = 380 + i * 205; card(d, (70, y0, 1010, y0 + 185))
            d.text((110, y0 + 32), s["name"], font=F("ExtraBold", 46), fill=INK)
            d.text((970, y0 + 32), pct(s["chg"]), font=F("ExtraBold", 46), fill=col(s["chg"]), anchor="ra")
            w = WY.get(sym) or {}; line = w.get("line") or ""; tag = w.get("tone", "중립")
            if (not line or "뚜렷한" in line) and w.get("title"):  # 이유가 없으면 그날 실제 기사 제목
                line, tag = w["title"].rstrip(".…") + f" ({w.get('src', '')})", "뉴스"
            line = _clean(line or "뚜렷한 개별 소식은 없었어요")
            tc = {"호재": UP, "악재": DOWN, "뉴스": LAVD}.get(tag, MUTED)
            bg = {"호재": (255, 236, 241), "악재": (232, 240, 255), "뉴스": (232, 240, 255)}.get(tag, (240, 241, 246))
            d.rounded_rectangle((110, y0 + 108, 190, y0 + 150), 12, fill=bg)
            d.text((150, y0 + 129), tag, font=F("Bold", 26), fill=tc, anchor="mm")
            ls = _wrap(d, line, f30, 760)
            d.text((210, y0 + 112), ls[0] + ("…" if len(ls) > 1 else ""), font=f30, fill=INK)
        return im

    movers(2, "많이 오른 종목", ranked[:4]).save(dst / "2.png")
    movers(3, "많이 내린 종목", ranked[-4:][::-1]).save(dst / "3.png")

    # 4. 수급
    im, d = base(4, "누가 사고 팔았나", "순매수 (억 원) · 빨강=샀다 파랑=팔았다")
    for i, (lab, key) in enumerate([("코스피", "KOSPI"), ("코스닥", "KOSDAQ")]):
        v = mf[key]; y0 = 360 + i * 400; card(d, (70, y0, 1010, y0 + 370))
        d.text((110, y0 + 34), lab, font=F("ExtraBold", 48), fill=INK)
        mx = max(abs(v["frg"]), abs(v["org"]), abs(v["ind"]), 1)
        for j, (who, val) in enumerate([("외국인", v["frg"]), ("기관", v["org"]), ("개인", v["ind"])]):
            y = y0 + 130 + j * 82; cx, half = 560, 220; L = int(abs(val) / mx * half)
            d.text((110, y), who, font=F("Bold", 36), fill=MUTED)
            d.rectangle((cx, y + 4, cx + 2, y + 44), fill=(200, 200, 215))
            if val >= 0: d.rounded_rectangle((cx, y + 6, cx + max(L, 6), y + 42), 10, fill=UP)
            else: d.rounded_rectangle((cx - max(L, 6), y + 6, cx, y + 42), 10, fill=DOWN)
            d.text((970, y), eok(val), font=F("ExtraBold", 36), fill=col(val), anchor="ra")
    b5 = fx.get("대형주_수급_5일") or {}
    if b5:
        d.text((80, 1188), f"대형주 최근 5일: 외국인 {eok(b5['frg'])} · 기관 {eok(b5['org'])}", font=F("Bold", 34), fill=INK)
    im.save(dst / "4.png")

    # 5. 내일 체크 포인트 + 진행자 인사 + 앱 안내
    im, d = base(5, "내일 체크 포인트")
    ma = fx.get("대형주_20일선_위_비율") or {}
    pts = [f"외국인이 계속 파는지 (오늘 코스피 {eok(mf['KOSPI']['frg'])})" if mf["KOSPI"]["frg"] < 0
           else f"외국인 매수가 이어지는지 (오늘 코스피 {eok(mf['KOSPI']['frg'])})",
           f"국제유가 (한 달 {pct(fx['WTI_20일%'])})",
           f"미국 10년 금리 {fx['미국10년물']}% · VIX {fx['VIX']}",
           f"원/달러 {sc['market']['usdkrw']['v']:,.0f}원 · 코스피 1주 {pct(fx['코스피']['5일'])}"]
    if ma and len(pts) < 5: pts.append(f"20일선 위 대형주 {ma['20일선_위']}/{ma['전체']}종목")
    for i, t in enumerate(pts):
        y = 300 + i * 88
        d.ellipse((80, y + 10, 116, y + 46), fill=LAVD); d.text((98, y + 28), str(i + 1), font=F("Bold", 26), fill=WHITE, anchor="mm")
        d.text((140, y + 2), t, font=F("Bold", 40), fill=INK)
    d.text((540, 728), "▼ 오늘의 분석과 내일 전망 전문은 캡션 '더 보기'에서", font=F("Bold", 28), fill=LAVD, anchor="mm")  # 2026-10-31 사용자: 더보기 유도
    card(d, (70, 760, 1010, 1250))
    ph = _photo(hid, 240, 320, 28); im.paste(ph[0], (100, 790), ph[1])
    d.text((370, 795), f"오늘은 {gsub}", font=F("ExtraBold", 44), fill=INK)
    d.text((370, 855), "전해 드렸어요", font=F("Medium", 34), fill=MUTED)
    d.text((370, 920), "평일 17시 50분,", font=F("Medium", 32), fill=INK)  # 2026-10-29 사용자: 'AI 직원 11명' 문구 빼기
    d.text((370, 962), "장마감을 1분으로 정리해 드려요", font=F("Medium", 32), fill=INK)
    d.rounded_rectangle((370, 1030, 975, 1100), 34, fill=LAVD)
    d.text((672, 1065), "팔로우하고 내일도 받아보기", font=F("Bold", 34), fill=WHITE, anchor="mm")
    d.rounded_rectangle((100, 1130, 980, 1225), 22, fill=UP)
    d.text((540, 1160), "실전 데이터 모의투자 앱 선착순 무료 배포", font=F("ExtraBold", 36), fill=WHITE, anchor="mm")
    parts = [("댓글에 ", F("Medium", 30)), ("'연구소'", F("ExtraBold", 33)), (" 남겨주세요", F("Medium", 30))]
    tw = sum(d.textlength(t, font=f) for t, f in parts); x = 540 - tw / 2  # 가운데 정렬
    for t, f in parts: d.text((x, 1203), t, font=f, fill=WHITE, anchor="lm"); x += d.textlength(t, font=f)
    im.save(dst / "5.png")

    # 캡션 첫 줄 = 피드에서 잘리기 전에 보이는 한 줄. 사실 나열 대신 그날 가장 크게 움직인 종목으로 궁금증을 건다
    # (2026-10-29 미라 분석: "윤시아가 알려주는…"로 시작하면 넘겨 볼 이유가 없음). 권유·추천 표현은 쓰지 않음
    big = max(S.values(), key=lambda x: abs(x["chg"]))
    mood = "급등" if k["chg"] >= 2 else "급락" if k["chg"] <= -2 else "상승" if k["chg"] > 0 else "하락"
    hook = (f"{'📈' if k['chg'] >= 0 else '📉'} 코스피 {pct(k['chg'])} {mood}한 날, "
            f"{big['name']} {pct(big['chg'])} {'왜 올랐을까?' if big['chg'] > 0 else '왜 빠졌을까?'}")
    # 2026-10-31 사용자: "현황만이 아니라 분석이랑 전망이 있어야 더보기 눌러서 본다" → 둘째 줄에 예고, 본문에 분석·내일 체크 포인트
    bsym = next((sy for sy, x in S.items() if x is big), None)
    def why_of(sym):
        w = WY.get(sym) or {}; line = w.get("line") or ""; nm = (S.get(sym) or {}).get("name", "")
        if (not line or "뚜렷한" in line) and w.get("title") and nm and nm[:2] in w["title"]:  # 그 종목 기사일 때만 제목을 씀
            line = w["title"].rstrip(".…") + (f" ({w['src']})" if w.get("src") else "")
        return _clean(line) if line and "뚜렷한" not in line else "뚜렷한 개별 소식은 없었어요"
    def amt(x):  # 문장 속 금액: 부호 없이, 1만 억 넘으면 조
        n = abs(round(x)); j, r = divmod(n, 10000)
        return f"{j}조 {r:,}억" if j and r else f"{j}조" if j else f"{n:,}억"
    fk, ok_ = mf["KOSPI"]["frg"], mf["KOSPI"]["org"]
    flow_txt = (f"외국인이 {amt(fk)} 팔고, 기관이 {amt(ok_)} 받아 냈어요" if fk < 0 < ok_ else
                f"외국인 {amt(fk)}, 기관 {amt(ok_)} 함께 샀어요" if fk > 0 and ok_ > 0 else
                f"외국인 {amt(fk)}, 기관 {amt(ok_)} 함께 팔고 개인이 받았어요" if fk < 0 and ok_ < 0 else
                f"외국인이 {amt(fk)} 사고, 기관이 {amt(ok_)} 팔았어요")
    breadth = ("대부분 오른 하루" if up > dn * 1.5 else "대부분 내린 하루" if dn > up * 1.5 else "종목마다 엇갈린 하루")
    tone = o.get("tone") if o.get("date") == date and o.get("source") != "규칙" else None
    analysis = "\n".join([
        f"• 시장: {breadth}였어요. 대형주 {len(S)}종목 중 {up}개 오르고 {dn}개 내렸어요" + (f" (분위기 '{tone}')" if tone else ""),
        f"• 수급: {flow_txt}",
        f"• {big['name']} {pct(big['chg'])}: {why_of(bsym)}",
        *[f"• {x['name']} {pct(x['chg'])}: {why_of(sy)}" for sy, x in (ranked[0], ranked[-1]) if x is not big],
    ])
    checks = "\n".join(f"{i + 1}) {t}" for i, t in enumerate(pts[:3]))
    teaser = f"👇 {big['name']} {'왜 올랐는지' if big['chg'] > 0 else '왜 빠졌는지'} · 내일 체크 포인트 3가지 (더 보기)"
    caption = f"""{hook}
{teaser}

{gsub} 전해주는 {md} 장마감 · 코스피 {pct(k['chg'])} · 코스닥 {pct(q['chg'])}
🔎 오늘 주식 시황 · 코스피 마감 · {' · '.join(dict.fromkeys(s['name'] + ' 주가' for s in (big, ranked[0][1], ranked[-1][1])))}

코스피 {k['v']:,.2f} ({pct(k['chg'])}) · 코스닥 {q['v']:,.2f} ({pct(q['chg'])})
대형주 {len(S)}종목 중 {up}개 상승 · {dn}개 하락
외국인 코스피 {eok(mf['KOSPI']['frg'])} · 기관 {eok(mf['KOSPI']['org'])}

🔺 많이 오른: {', '.join(s['name'] + ' ' + pct(s['chg']) for _, s in ranked[:3])}
🔻 많이 내린: {', '.join(s['name'] + ' ' + pct(s['chg']) for _, s in ranked[-3:][::-1])}

🧐 오늘의 분석
{analysis}

🔭 내일 체크 포인트
{checks}

👉 팔로우하면 평일 17시 50분, 장마감 요약을 매일 받아볼 수 있어요
🎁 실전 데이터 모의투자 앱 선착순 무료 배포 중! 댓글에 '연구소' 남기면 DM으로 바로 보내 드려요

※ 공개 시세로 만든 참고 자료이며 투자 권유가 아닙니다. 투자 판단과 책임은 본인에게 있습니다.

#장마감브리핑 #퇴근길주식 #국내주식"""
    (dst / "caption.txt").write_text(caption, encoding="utf-8")
    def mv(sym, s):  # 릴스용: 이름·등락률·한 줄 이유
        w = WY.get(sym) or {}; line = w.get("line") or ""
        if (not line or "뚜렷한" in line) and w.get("title"): line = w["title"].rstrip(".…")
        return {"name": s["name"], "chg": round(s["chg"], 2), "why": _clean(line) if line else ""}
    reel = {"gname": gname, "gsub": gsub, "kospi": {"v": k["v"], "chg": round(k["chg"], 2)},
            "kosdaq": {"v": q["v"], "chg": round(q["chg"], 2)}, "n": len(S), "up": up, "dn": dn,
            "big": {"name": big["name"], "chg": round(big["chg"], 2)},
            "top": [mv(a, b) for a, b in ranked[:3]], "bottom": [mv(a, b) for a, b in ranked[-3:][::-1]],
            "flow": {key: {w: round(mf[key][w]) for w in ("frg", "org", "ind")} for key in ("KOSPI", "KOSDAQ") if key in mf}}
    info = {"date": date, "host": hid, "hostName": hname, "next": nname,
            "images": [f"cards/{i}.png" for i in range(1, N + 1)], "caption": caption, "reel": reel}
    (dst / "cards.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "web/data"))["caption"])
