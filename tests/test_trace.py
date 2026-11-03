from ai_trading.data.trace import marks_of, build


def _flat(n=80, v=1000, p=100):
    return [p] * n, [p + 1] * n, [p - 1] * n, [p] * n, [v] * n


def test_mark_needs_base_volume_and_up_close():
    o, h, l, c, v = _flat()
    c[75], h[75], l[75], v[75] = 103, 104, 100, 5000   # 옆걸음 중 거래량 5배 + 위쪽 마감
    m = marks_of(o, h, l, c, v)
    assert [x["i"] for x in m] == [75] and m[0]["vr"] == 5.0


def test_no_mark_when_down_close_or_flow_selling():
    o, h, l, c, v = _flat()
    c[75], h[75], l[75], v[75] = 98, 101, 97, 5000      # 내리며 마감
    assert marks_of(o, h, l, c, v) == []
    c[75], h[75], l[75] = 103, 104, 100
    assert marks_of(o, h, l, c, v, {75: -10}) == []     # 기관·외국인 순매도


def test_no_mark_after_big_run_up():
    o, h, l, c, v = _flat()
    for k in range(55, 75): c[k] = h[k] = 100 + (k - 54) * 2; l[k] = c[k] - 1   # 20일간 급등(옆걸음 아님)
    c[75], h[75], l[75], v[75] = 145, 146, 140, 5000
    assert marks_of(o, h, l, c, v) == []


def test_build_has_report_and_items():
    o, h, l, c, v = _flat(120)
    c[90], h[90], l[90], v[90] = 103, 104, 100, 5000
    dates = [f"2026-01-{k:03d}" for k in range(120)]
    r = build({"A": {"name": "가", "code": "1", "o": o, "h": h, "l": l, "c": c, "v": v}}, dates, {})
    assert "A" in r["items"] and r["items"]["A"]["marks"][0]["n"] == 1 and r["stats"]["signal"]["n"] == 1
