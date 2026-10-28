import json

from ai_trading.data.rebound import build


def _stock():
    # 60일 횡보 → 15% 급락 → 긴 아래꼬리 → 거래량 늘며 반등
    c = [100.0] * 60 + [97, 94, 90, 87, 85, 86, 88, 90, 91, 92]
    o = c[:]; h = [x + 1 for x in c]; l = [x - 1 for x in c]; v = [1000] * 65 + [3000] * 5
    l[64] = 78; o[64] = 85.5; c[64] = 85; h[64] = 86  # 아래꼬리 긴 날
    return {"code": "000001", "name": "테스트", "o": o, "h": h, "l": l, "c": c, "v": v}


def test_rebound_finds_bottom_and_is_json_safe():
    dates = [f"2026-08-{i:02d}" for i in range(1, 31)] + [f"2026-09-{i:02d}" for i in range(1, 31)] + [f"2026-10-{i:02d}" for i in range(1, 11)]
    flows = [{"date": d, "frg": 10, "org": 5, "ind": -15} for d in dates[-5:]]
    r = build({"T.KS": _stock()}, dates, {"000001": flows})
    json.dumps(r)  # numpy bool 이 섞이면 저장이 깨짐
    assert r["items"] and r["items"][0]["checks"]["drop"]["ok"]
    ck = r["items"][0]["checks"]
    assert ck["tail"]["ok"] and ck["volume"]["ok"] and ck["flow"]["ok"]


def test_no_drop_no_item():
    s = _stock(); s["c"] = [100.0] * 70; s["l"] = [99.0] * 70; s["h"] = [101.0] * 70; s["o"] = [100.0] * 70
    dates = [f"d{i}" for i in range(70)]
    assert build({"T.KS": s}, dates, {})["items"] == []
