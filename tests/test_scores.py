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


from ai_trading.data.scores import fin_score, tech_score, top_headlines


def test_fin_score_uses_only_released_quarters():
    f = {"equity": 1000.0, "liabilities": 400.0, "shares": 10.0, "div_1y": 1.0,
         "quarters": [{"date": f"2026-0{m}-01", "rev": 100.0, "op": 20.0, "ni": 15.0} for m in range(1, 6)]
                     + [{"date": "2026-09-01", "rev": 100.0, "op": -50.0, "ni": -50.0}]}
    sc, m = fin_score(f, 100.0, "2026-06-30")
    assert m["roe"] == 6.0 and m["per"] == round(1000 / 60, 2) and m["debt"] == 40.0 and m["margin"] == 20.0
    assert 0 <= sc <= 5
    assert fin_score(None, 100.0, "2026-06-30") == (None, {})


def test_tech_score_trend():
    up = pd.DataFrame({"Close": np.linspace(100, 130, 150)})
    up["High"], up["Low"], up["Volume"] = up.Close * 1.01, up.Close * 0.99, 1000.0
    down = up.iloc[::-1].reset_index(drop=True)
    su, sigs = tech_score(up)
    sd, _ = tech_score(down)
    assert su > sd and 0 <= sd <= su <= 5 and len(sigs) == 12


def test_top_headlines_newest_unique():
    items = [{"date": "2026-10-01", "title": "a"}, {"date": "2026-10-03", "title": "b"},
             {"date": "2026-10-02", "title": "b"}, {"date": "2026-10-02", "title": "c"}]
    assert [x["title"] for x in top_headlines(items)] == ["b", "c", "a"]
