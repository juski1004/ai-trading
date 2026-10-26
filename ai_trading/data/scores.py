"""앱 홈·분석 화면용 종목별 AI 점수 (data/scores.json).

market.json 과 같은 모양의 dict 를 받아 종목마다 AI 4명(JOY·OSCAR·RAY·MILES)의 점수와
LLOYD 리스크 점검을 계산한다. 앱에서는 '매수/매도' 대신 '긍정/중립/부정'으로 표시한다(참고용).

  python -m ai_trading.data.scores web/data      이미 만든 market.json·news.json 으로 다시 계산
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from ..agents import WEIGHTS, atr_pct, joy, lloyd, miles, oscar, ray, rsi
from ..config import GameRules
from ..signals import news_score

LABELS = (("긍정", 0.3), ("부정", -0.3))


def label_of(score: float) -> str:
    if score >= LABELS[0][1]:
        return "긍정"
    if score <= LABELS[1][1]:
        return "부정"
    return "중립"


def risk_level(ok: bool, vol: float) -> str:
    return "높음" if not ok or vol > 4.5 else "보통" if vol > 2.5 else "낮음"


def fin_score(f: dict | None, price: float, asof: str) -> tuple[float | None, dict]:
    """재무 점수 0~5 (ROE·PER·부채비율·영업이익률·영업이익 전년비). 발표된 분기만 쓴다."""
    if not f:
        return None, {}
    qs = [q for q in f.get("quarters", []) if q.get("op") is not None and q.get("rev") and q.get("date", "") <= asof]
    last4 = qs[-4:]
    ni = sum((q.get("ni") if q.get("ni") is not None else q["op"] * 0.75) for q in last4)
    op, rev = sum(q["op"] for q in last4), sum(q["rev"] for q in last4)
    eq, liab, sh = f.get("equity"), f.get("liabilities"), f.get("shares")
    m, parts = {}, []
    if eq and eq > 0 and last4:
        m["roe"] = ni / eq * 100
        parts.append(1 if m["roe"] >= 15 else .75 if m["roe"] >= 10 else .5 if m["roe"] >= 5 else .25 if m["roe"] > 0 else 0)
    if sh and last4:
        m["per"] = price * sh / ni if ni > 0 else None
        p = m["per"]
        parts.append(0 if p is None else 1 if p < 8 else .8 if p < 12 else .6 if p < 20 else .35 if p < 35 else .15)
        if eq and eq > 0:
            m["pbr"] = price * sh / eq
    if eq and eq > 0 and liab is not None:
        m["debt"] = liab / eq * 100
        parts.append(1 if m["debt"] < 50 else .75 if m["debt"] < 100 else .5 if m["debt"] < 200 else .25)
    if rev > 0:
        m["margin"] = op / rev * 100
        parts.append(1 if m["margin"] >= 15 else .7 if m["margin"] >= 8 else .4 if m["margin"] >= 3 else .2 if m["margin"] > 0 else 0)
    if len(qs) >= 5 and qs[-5]["op"]:
        m["op_yoy"] = (qs[-1]["op"] / abs(qs[-5]["op"]) - 1) * 100
        y = m["op_yoy"]
        parts.append(1 if y > 20 else .75 if y > 5 else .5 if y > -5 else .25 if y > -20 else 0)
    if f.get("div_1y"):
        m["div_yield"] = f["div_1y"] / price * 100
    m = {k: (round(v, 2) if v is not None else None) for k, v in m.items()}
    return (round(sum(parts) / len(parts) * 5, 1) if len(parts) >= 2 else None), m


def tech_score(df: pd.DataFrame) -> tuple[float, list]:
    """기술 점수 0~5: 지표 12개의 매수(B)·매도(S)·중립(N) 신호 비율."""
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    last = c.iloc[-1]
    sig = []
    for n in (5, 20, 60, 120):
        ma = c.rolling(n).mean().iloc[-1]
        if pd.notna(ma):
            sig.append((f"{n}일 이동평균", round(ma), "B" if last > ma else "S"))
    ma5, ma20 = c.rolling(5).mean().iloc[-1], c.rolling(20).mean().iloc[-1]
    sig.append(("이평 배열 5/20", "정배열" if ma5 > ma20 else "역배열", "B" if ma5 > ma20 else "S"))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    sg = macd.ewm(span=9, adjust=False).mean()
    sig.append(("MACD", "시그널 위" if macd.iloc[-1] > sg.iloc[-1] else "시그널 아래", "B" if macd.iloc[-1] > sg.iloc[-1] else "S"))
    r = rsi(c)
    sig.append(("RSI 14", round(r, 1), "B" if r < 30 else "S" if r > 70 else "N"))
    hh, ll = h.rolling(14).max(), l.rolling(14).min()
    k = ((c - ll) / (hh - ll).replace(0, float("nan")) * 100).rolling(3).mean()
    kv = k.iloc[-1]
    sig.append(("스토캐스틱", round(kv, 1) if pd.notna(kv) else "-", "B" if kv < 20 else "S" if kv > 80 else "N"))
    wr = ((hh.iloc[-1] - last) / (hh.iloc[-1] - ll.iloc[-1]) * -100) if hh.iloc[-1] != ll.iloc[-1] else -50
    sig.append(("윌리엄스 %R", round(wr, 1), "B" if wr < -80 else "S" if wr > -20 else "N"))
    tp = (h + l + c) / 3
    md = tp.rolling(20).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
    cci = ((tp - tp.rolling(20).mean()) / (0.015 * md)).iloc[-1]
    sig.append(("CCI 20", round(cci, 1), "B" if cci < -100 else "S" if cci > 100 else "N"))
    mid, sd = c.rolling(20).mean().iloc[-1], c.rolling(20).std(ddof=0).iloc[-1]
    sig.append(("볼린저밴드", "상단 돌파" if last > mid + 2 * sd else "하단 이탈" if last < mid - 2 * sd else "밴드 안",
                "S" if last > mid + 2 * sd else "B" if last < mid - 2 * sd else "N"))
    obv = (v * c.diff().apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)).cumsum()
    sig.append(("OBV", "20일 평균 위" if obv.iloc[-1] > obv.rolling(20).mean().iloc[-1] else "20일 평균 아래",
                "B" if obv.iloc[-1] > obv.rolling(20).mean().iloc[-1] else "S"))
    nb, ns = sum(x[2] == "B" for x in sig), sum(x[2] == "S" for x in sig)
    return round(((nb - ns) / len(sig) + 1) / 2 * 5, 1), [list(x) for x in sig]


def top_headlines(items: list[dict], n: int = 3) -> list[dict]:
    seen, out = set(), []
    for x in sorted(items or [], key=lambda x: x.get("date", ""), reverse=True):
        if x.get("title") and x["title"] not in seen:
            seen.add(x["title"])
            out.append({k: x.get(k) for k in ("date", "title", "src", "link", "score")})
        if len(out) >= n:
            break
    return out


def _frame(bars: dict) -> pd.DataFrame:
    return pd.DataFrame({"Open": bars["o"], "High": bars["h"], "Low": bars["l"], "Close": bars["c"],
                         "Volume": bars.get("v", [0] * len(bars["c"]))}, dtype=float)


def build_scores(market: dict, news_sym: dict | None = None, fin: dict | None = None, rules: GameRules = GameRules()) -> dict:
    dates = market["dates"]
    today = date.fromisoformat(dates[-1])
    index_df = _frame(market["index"]) if market.get("index") else None
    stocks = {}
    for sym, st in market["stocks"].items():
        df = _frame(st)
        if len(df) < 60:
            continue
        ns = news_score(news_sym.get(sym, []), today) if news_sym else None
        ops = [joy(index_df, "코스피")] if index_df is not None else []
        ops += [oscar(df, ns), ray(df)]
        m_op, plan = miles(df, rules, max_qty=1)
        ops.append(m_op)
        w = sum(WEIGHTS[o.agent] for o in ops)
        score = sum(WEIGHTS[o.agent] * o.score for o in ops) / w
        risk = lloyd(df, rules, held=False, n_positions=0, daily_pnl_pct=0.0, max_qty=1)
        vol = atr_pct(df)
        c, v = df["Close"], df["Volume"]
        avg_vol = v.iloc[-21:-1].mean()
        stocks[sym] = {
            "name": st["name"], "code": st["code"], "market": st["market"],
            "price": round(float(c.iloc[-1])), "chg": round((c.iloc[-1] / c.iloc[-2] - 1) * 100, 2),
            # 그날 시가·고가·저가: 앱 지정가 주문 체결 확인용 (저가 ≤ 매수 지정가, 고가 ≥ 매도 지정가)
            "o": round(float(df["Open"].iloc[-1])), "h": round(float(df["High"].iloc[-1])), "l": round(float(df["Low"].iloc[-1])),
            "vol_ratio": round(float(v.iloc[-1] / avg_vol), 2) if avg_vol else None,
            "score": round(score, 3), "label": label_of(score),
            "opinions": [{"agent": o.agent, "score": round(o.score, 3), "summary": o.summary} for o in ops],
            "target": round(plan["target"]), "stop": round(plan["stop"]),
            "risk": {"level": risk_level(risk.approved, vol), "vol": round(vol, 2), "reasons": risk.reasons},
        }
        fs, fm = fin_score((fin or {}).get(sym), float(c.iloc[-1]), dates[-1])
        ts, tsig = tech_score(df)
        stocks[sym].update({"fin_score": fs, "fin": fm, "tech_score": ts, "tech": tsig,
                            "news": top_headlines((news_sym or {}).get(sym)),
                            "closes": [round(float(x)) for x in c.iloc[-120:]]})
    return {"date": dates[-1], "market": market_summary(market), "stocks": stocks}


def market_summary(market: dict) -> dict:
    """홈 화면 맨 위: 코스피·코스닥·원달러 마지막 값과 하루 변화율."""
    def last2(arr):
        vals = [x for x in arr if x is not None]
        return (vals[-1], (vals[-1] / vals[-2] - 1) * 100) if len(vals) >= 2 else (None, None)

    out = {}
    series = {"kospi": (market.get("index") or {}).get("c") or market["macro"].get("kospi"),
              "kosdaq": market["macro"].get("kosdaq"), "usdkrw": market["macro"].get("usdkrw")}
    for k, arr in series.items():
        v, chg = last2(arr or [])
        if v is not None:
            out[k] = {"v": round(v, 2), "chg": round(chg, 2)}
    return out


def main() -> None:
    d = Path(sys.argv[1] if len(sys.argv) > 1 else "web/data")
    market = json.loads((d / "market.json").read_text(encoding="utf-8"))
    news = json.loads((d / "news.json").read_text(encoding="utf-8")) if (d / "news.json").exists() else {}
    fin = json.loads((d / "fin.json").read_text(encoding="utf-8")) if (d / "fin.json").exists() else {}
    out = build_scores(market, news.get("sym"), fin)
    (d / "scores.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"AI 점수 {len(out['stocks'])}종목 → {d / 'scores.json'}")


if __name__ == "__main__":
    main()
