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

from ..agents import WEIGHTS, atr_pct, joy, lloyd, miles, oscar, ray
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


def _frame(bars: dict) -> pd.DataFrame:
    return pd.DataFrame({"Open": bars["o"], "High": bars["h"], "Low": bars["l"], "Close": bars["c"],
                         "Volume": bars.get("v", [0] * len(bars["c"]))}, dtype=float)


def build_scores(market: dict, news_sym: dict | None = None, rules: GameRules = GameRules()) -> dict:
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
            "vol_ratio": round(float(v.iloc[-1] / avg_vol), 2) if avg_vol else None,
            "score": round(score, 3), "label": label_of(score),
            "opinions": [{"agent": o.agent, "score": round(o.score, 3), "summary": o.summary} for o in ops],
            "target": round(plan["target"]), "stop": round(plan["stop"]),
            "risk": {"level": risk_level(risk.approved, vol), "vol": round(vol, 2), "reasons": risk.reasons},
        }
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
    out = build_scores(market, news.get("sym"))
    (d / "scores.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"AI 점수 {len(out['stocks'])}종목 → {d / 'scores.json'}")


if __name__ == "__main__":
    main()
