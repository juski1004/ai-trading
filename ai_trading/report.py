"""사용자 개인 보고 (2026-11-22 사용자: "투자연구소 앱은 이제 내가 쓰게 — 종목분석·종목추천·한국장/미국장 마감 브리핑
하루 두 번 보고, 월요일 추천 종목 진입가, 금요일 결과·예상 적중 여부").

  python -m ai_trading.report us                 미국장 마감 + 주요 뉴스 (평일 아침, 월요일은 금요일 밤 미국장 + 주말 뉴스)
  python -m ai_trading.report kr                 한국장 마감 (평일 오후)
  python -m ai_trading.report analyze 005930     종목 하나 분석
  python -m ai_trading.report picks 2026-11-23   월요일: 이번 주 추천 종목 + 진입가 → reports/picks/<월요일>.json
  python -m ai_trading.report result 2026-11-23  금요일: 그 주 추천 종목 결과 (상승/하락, 예상 적중)
  python -m ai_trading.report app am|pm say.txt [날짜]  앱 '본부장 보고' 파일 reports/app/<날짜>-<am|pm>.json
                                                 (오전 = 미국장+뉴스, 월요일은 추천 종목 포함 / 오후 = 한국장, 금요일은 주간 결과 포함)
                                                 → history_media 처럼 이 브랜치에 커밋 후 report-publish.yml 실행하면 앱 사이트 data/report/ 로

데이터: 앱 사이트(scores.json — AI 점수·목표가·손절가·위험도), 네이버 증권(국내 시세·지수), 야후(미국 지수·종목·환율·유가).
숫자만 모아 주는 도구이고, 해설은 Claude 가 이 숫자로 쓴다. 참고용, 투자 판단과 책임은 사용자 본인.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "https://juski1004.github.io/ai-trading/data/"
ROOT = Path(__file__).resolve().parent.parent
PICKS = ROOT / "reports" / "picks"
UA = {"User-Agent": "Mozilla/5.0"}
KST = dt.timezone(dt.timedelta(hours=9))


def get(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.loads(r.read())


def yahoo(sym: str) -> dict:
    """최근 2거래일 종가로 등락률."""
    j = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5d&interval=1d")["chart"]["result"][0]
    c = [x for x in j["indicators"]["quote"][0]["close"] if x is not None]
    last, prev = c[-1], c[-2]
    day = dt.datetime.fromtimestamp(j["meta"]["regularMarketTime"], dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-5))).date()
    return {"v": round(last, 2), "chg": round((last / prev - 1) * 100, 2), "date": str(day)}


def num(s) -> float:
    return float(str(s).replace(",", "")) if s not in (None, "") else float("nan")


def naver_index(code: str) -> dict:
    j = get(f"https://m.stock.naver.com/api/index/{code}/basic")
    return {"v": num(j["closePrice"]), "chg": num(j["fluctuationsRatio"])}


def naver_stock(code: str) -> dict:
    j = get(f"https://m.stock.naver.com/api/stock/{code}/basic")
    return {"name": j.get("stockName"), "v": num(j["closePrice"]), "chg": num(j["fluctuationsRatio"]), "time": j.get("localTradedAt", "")}


US = {"S&P500": "^GSPC", "나스닥": "^IXIC", "다우": "^DJI", "필라델피아 반도체": "^SOX", "VIX(공포지수)": "^VIX"}
US_STOCKS = {"엔비디아": "NVDA", "애플": "AAPL", "마이크로소프트": "MSFT", "아마존": "AMZN", "알파벳": "GOOGL", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO", "마이크론": "MU"}
MACRO = {"원/달러": "KRW=X", "WTI 유가": "CL=F", "미국 10년 금리": "^TNX", "금": "GC=F"}


def line(name, d, unit=""):
    arrow = "▲" if d["chg"] > 0 else "▼" if d["chg"] < 0 else "-"
    return f"- {name}: {d['v']:,}{unit} ({arrow} {d['chg']:+.2f}%)"


def us() -> str:
    out = ["## 미국장 마감"]
    for n, s in US.items(): out.append(line(n, yahoo(s)))
    out.append("\n### 주요 종목")
    rows = sorted(((n, yahoo(s)) for n, s in US_STOCKS.items()), key=lambda x: -abs(x[1]["chg"]))
    out += [line(n, d, " $") for n, d in rows]
    out.append("\n### 환율·원자재·금리")
    for n, s in MACRO.items(): out.append(line(n, yahoo(s)))
    return "\n".join(out) + "\n" + news()


def news(n: int = 10) -> str:
    """주요 경제 뉴스 (네이버 증권 주요뉴스 + 앱이 모은 경제 뉴스). 월요일 아침엔 주말 뉴스까지."""
    out = ["\n### 주요 뉴스"]; seen = set()
    try:
        for x in get(f"https://m.stock.naver.com/api/news/list?category=mainnews&pageSize={n}&page=1"):
            t = x.get("tit", "").strip()
            if t and t not in seen:
                seen.add(t); out.append(f"- [{x.get('ohnm', '')} {x.get('dt', '')[4:6]}/{x.get('dt', '')[6:8]} {x.get('dt', '')[8:10]}:{x.get('dt', '')[10:12]}] {t}")
                if x.get("subcontent"): out.append(f"  - {x['subcontent'][:110]}")
    except Exception as e:
        out.append(f"- (네이버 뉴스 실패: {type(e).__name__})")
    try:
        eco = sorted(get(SITE + "news.json").get("eco", []), key=lambda x: x.get("date", ""), reverse=True)[:5]
        out += [f"- [{x.get('src', '')} {x.get('date', '')}] {x['title']}" for x in eco if x["title"] not in seen]
    except Exception:
        pass
    return "\n".join(out)


def scores() -> dict:
    return get(SITE + "scores.json")


def kr() -> str:
    out = ["## 한국장 마감", line("코스피", naver_index("KOSPI")), line("코스닥", naver_index("KOSDAQ"))]
    sc = scores()["stocks"]; live = []
    for k, s in sc.items():
        try: live.append((s, naver_stock(s["code"])))
        except Exception: pass
    live.sort(key=lambda x: -x[1]["chg"])
    out.append("\n### 분석 대상 종목 중 많이 오른 5")
    out += [f"- {s['name']}: {d['v']:,.0f}원 ({d['chg']:+.2f}%) · AI {s['label']}" for s, d in live[:5]]
    out.append("\n### 많이 내린 5")
    out += [f"- {s['name']}: {d['v']:,.0f}원 ({d['chg']:+.2f}%) · AI {s['label']}" for s, d in live[-5:][::-1]]
    out.append(f"\n### AI 점수 상위 5 (앱 기준 {scores()['date']}, 다음 날 참고)")
    top = sorted(sc.values(), key=lambda s: -s["score"])[:5]
    out += [f"- {s['name']}: 점수 {s['score']:+.2f} ({s['label']}) · 목표 {s.get('target', 0):,} · 손절 {s.get('stop', 0):,} · 위험 {s.get('risk', {}).get('level', '-')}" for s in top]
    return "\n".join(out)


def analyze(code: str) -> str:
    sc = scores()["stocks"]; s = next((v for v in sc.values() if v["code"] == code), None); d = naver_stock(code)
    out = [f"## {d['name']} ({code}) 분석", f"- 현재가 {d['v']:,.0f}원 ({d['chg']:+.2f}%)"]
    if s:
        out.append(f"- 앱 AI 점수 {s['score']:+.2f} ({s['label']}) · 목표 {s.get('target', 0):,} · 손절 {s.get('stop', 0):,} · 위험 {s.get('risk', {}).get('level', '-')} {s.get('risk', {}).get('reasons', [])}")
        out += [f"- {o['agent']}: {o['summary']} ({o['score']:+.2f})" for o in s.get("opinions", [])]
    else:
        out.append("- 앱 분석 대상(78종목)에 없는 종목 → 시세만")
    return "\n".join(out)


def picks(monday: str, n: int = 3) -> str:
    """AI 점수 높은 순, 위험 '높음' 제외, 3종목. 진입가 = 지금(월요일 장 전이면 직전 거래일 종가) 가격."""
    sc = scores()["stocks"]
    cand = [s for s in sorted(sc.values(), key=lambda s: -s["score"]) if s.get("risk", {}).get("level") != "높음" and s["score"] > 0][:n]
    rows = []
    for s in cand:
        d = naver_stock(s["code"])
        rows.append({"code": s["code"], "name": s["name"], "entry": d["v"], "target": s.get("target"), "stop": s.get("stop"),
                     "score": s["score"], "label": s["label"], "risk": s.get("risk", {}).get("level"), "expect": "상승",
                     "why": [o["summary"] for o in s.get("opinions", [])]})
    PICKS.mkdir(parents=True, exist_ok=True)
    (PICKS / f"{monday}.json").write_text(json.dumps({"monday": monday, "picks": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    out = [f"## 이번 주 추천 종목 ({monday} 주 · 앱 AI 점수 기준일 {scores()['date']})"]
    for r in rows:
        out.append(f"- **{r['name']}** ({r['code']}) 진입가 {r['entry']:,.0f}원 · 목표 {r['target']:,} · 손절 {r['stop']:,} · 예상 {r['expect']} · AI {r['score']:+.2f} · 위험 {r['risk']}")
        out += [f"  - {w}" for w in r["why"]]
    if not rows: out.append("- 조건(AI 점수 플러스·위험 높음 아님)에 맞는 종목 없음 → 이번 주는 쉬어 감")
    return "\n".join(out)


def result(monday: str) -> str:
    p = json.loads((PICKS / f"{monday}.json").read_text(encoding="utf-8"))
    out = [f"## 이번 주 추천 종목 결과 ({monday} 주)"]; hit = 0
    for r in p["picks"]:
        d = naver_stock(r["code"]); ret = (d["v"] / r["entry"] - 1) * 100
        up = ret > 0; flat = abs(ret) < 0.005; ok = (not flat) and up == (r["expect"] == "상승"); hit += ok
        tag = "목표가 도달" if r.get("target") and d["v"] >= r["target"] else "손절가 이탈" if r.get("stop") and d["v"] <= r["stop"] else ""
        out.append(f"- {r['name']}: 진입 {r['entry']:,.0f} → 금요일 {d['v']:,.0f}원 ({ret:+.2f}%) · {'보합' if flat else '상승' if up else '하락'} · 예상 {r['expect']} → {'➖ 보합' if flat else '✅ 적중' if ok else '❌ 빗나감'} {tag}")
    if p["picks"]: out.append(f"\n적중 {hit}/{len(p['picks'])}")
    return "\n".join(out)


def md_sections(md: str) -> list[dict]:
    """보고 마크다운 → 앱 화면용 [{h, items:[{t, sub:[]}]}]."""
    out = []
    for ln in md.splitlines():
        if ln.startswith("#"):
            out.append({"h": ln.lstrip("#").strip().replace("**", ""), "items": []})
        elif ln.startswith("  - ") and out and out[-1]["items"]:
            out[-1]["items"][-1]["sub"].append(ln[4:].strip())
        elif ln.startswith("- "):
            if not out: out.append({"h": "", "items": []})
            out[-1]["items"].append({"t": ln[2:].strip().replace("**", ""), "sub": []})
        elif ln.strip() and out:
            out[-1]["items"].append({"t": ln.strip(), "sub": []})
    return [x for x in out if x["items"]]


def app(slot: str, say_file: str, day: str | None = None) -> str:
    """앱 '본부장 보고' 파일: reports/app/<날짜>-<am|pm>.json (2026-11-23 사용자: 보고는 앱으로 본부장 보고로 오전·오후).
    say_file = 본부장 의견(Claude 가 숫자를 보고 쓴 3~6줄, 한 줄에 한 문장). 오전: 미국장+뉴스(+월요일 추천), 오후: 한국장(+금요일 결과)."""
    now = dt.datetime.now(KST); day = day or now.date().isoformat(); wd = dt.date.fromisoformat(day).weekday()
    monday = (dt.date.fromisoformat(day) - dt.timedelta(days=wd)).isoformat()
    md = us() if slot == "am" else kr()
    if slot == "am" and wd == 0: md += "\n" + picks(monday)
    if slot == "pm" and wd == 4 and (PICKS / f"{monday}.json").exists(): md += "\n" + result(monday)
    if slot == "pm" and wd != 4 and (PICKS / f"{monday}.json").exists():
        p = json.loads((PICKS / f"{monday}.json").read_text(encoding="utf-8"))["picks"]
        rows = []
        for r in p:
            d = naver_stock(r["code"]); rows.append(f"- {r['name']}: {d['v']:,.0f}원 (오늘 {d['chg']:+.2f}%, 진입가 대비 {(d['v'] / r['entry'] - 1) * 100:+.2f}%)")
        md += "\n### 이번 주 추천 종목 오늘\n" + "\n".join(rows)
    say = [l.strip() for l in Path(say_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    title = ("오전 보고 · 미국장 마감과 뉴스" + (" · 이번 주 추천 종목" if wd == 0 else "")) if slot == "am" else \
            ("오후 보고 · 한국장 마감" + (" · 이번 주 추천 결과" if wd == 4 else ""))
    j = {"date": day, "slot": slot, "at": "08:00" if slot == "am" else "16:50", "title": title, "say": say,
         "sections": md_sections(md), "made": now.strftime("%Y-%m-%d %H:%M"), "note": "참고용 정보입니다. 투자 판단과 책임은 본인에게 있어요."}
    d = ROOT / "reports" / "app"; d.mkdir(parents=True, exist_ok=True)
    f = d / f"{day}-{slot}.json"; f.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"저장: {f.relative_to(ROOT)} · 섹션 {len(j['sections'])}개"


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0]
    print({"us": lambda: us(), "kr": lambda: kr(), "analyze": lambda: analyze(a[1]),
           "picks": lambda: picks(a[1]), "result": lambda: result(a[1]),
           "app": lambda: app(a[1], a[2], a[3] if len(a) > 3 else None)}[cmd]())
