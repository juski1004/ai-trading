import numpy as np
import pandas as pd

from ai_trading.data.scores import build_scores, label_of, risk_level


def bars(closes):
    c = [float(x) for x in closes]
    return {"o": c, "h": [x * 1.01 for x in c], "l": [x * 0.99 for x in c], "c": c, "v": [1000] * len(c)}


def market(n=80):
    up, down = np.linspace(100, 104, n), np.linspace(130, 100, n)
    return {
        "dates": [d.date().isoformat() for d in pd.date_range("2026-07-01", periods=n)],
        "index": bars(up),
        "macro": {"kosdaq": list(np.linspace(800, 790, n)), "usdkrw": [1300.0] * (n - 1) + [1313.0]},
        "stocks": {
            "UP.KS": {"name": "오름", "code": "UP", "market": "KOSPI", **bars(up)},
            "DN.KS": {"name": "내림", "code": "DN", "market": "KOSPI", **bars(down)},
            "NEW.KQ": {"name": "신규", "code": "NEW", "market": "KOSDAQ", **bars(up[:30])},
        },
    }


def test_labels_and_risk():
    assert label_of(0.3) == "긍정" and label_of(-0.3) == "부정" and label_of(0.1) == "중립"
    assert risk_level(False, 1.0) == "높음" and risk_level(True, 3.0) == "보통" and risk_level(True, 1.0) == "낮음"


def test_build_scores_ranks_trend_and_skips_short_history():
    out = build_scores(market())
    s = out["stocks"]
    assert set(s) == {"UP.KS", "DN.KS"}
    assert s["UP.KS"]["score"] > s["DN.KS"]["score"]
    assert s["DN.KS"]["score"] < 0
    up = s["UP.KS"]
    assert up["stop"] < up["price"] < up["target"]
    assert [o["agent"] for o in up["opinions"]] == ["JOY", "OSCAR", "RAY", "MILES"]


def test_market_summary():
    m = build_scores(market())["market"]
    assert m["usdkrw"]["v"] == 1313.0 and m["usdkrw"]["chg"] == 1.0
    assert set(m) == {"kospi", "kosdaq", "usdkrw"}
