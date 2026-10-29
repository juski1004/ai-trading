import json

from ai_trading.data.growth import build


def _fin(op_last=30):
    q = [{"rev": 100, "op": 10}, {"rev": 105, "op": 11}, {"rev": 110, "op": 12}, {"rev": 115, "op": 13}, {"rev": 130, "op": op_last}]
    est = {"rev": [{"period": "올해", "growth": 0.3}, {"period": "내년", "growth": 0.2}],
           "eps": [{"period": "올해", "avg": 1000, "growth": 0.4}, {"period": "내년", "avg": 2000, "growth": 0.3}],
           "target": {"mean": 30000}, "rec": {"strongBuy": 5, "buy": 3, "hold": 1}}
    return {"quarters": q, "est": est}


def test_growth_pass_and_json_safe():
    sc = {"date": "2026-10-28", "stocks": {"A.KS": {"name": "가", "code": "000001", "price": 20000, "chg": 1.0},
                                           "B.KS": {"name": "나", "code": "000002", "price": 20000, "chg": 0.0}}}
    r = build(sc, {"A.KS": _fin(), "B.KS": {"quarters": [{"rev": 1, "op": None}] * 5, "est": {}}})
    json.dumps(r)
    assert [x["sym"] for x in r["items"]] == ["A.KS"] and r["items"][0]["score"] == 6
