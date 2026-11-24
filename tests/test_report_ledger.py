from ai_trading.report import simulate, _cum

R = {"entry": 100.0, "stop": 95.0, "target": 110.0}


def b(d, o, h, l, c):
    return {"d": d, "o": o, "h": h, "l": l, "c": c}


def test_stop_first_and_gap_down():
    r = simulate(R, [b("2026-11-23", 99, 101, 96, 98), b("2026-11-24", 93, 94, 90, 92)], 5)
    assert r["why"] == "손절" and r["exit"] == 93 and r["done"]


def test_take_profit():
    r = simulate(R, [b("2026-11-23", 101, 111, 100, 109)], 5)
    assert r["why"] == "익절" and r["exit"] == 110 and r["ret"] == 10.0


def test_same_day_both_counts_as_stop():
    assert simulate(R, [b("2026-11-23", 100, 112, 94, 105)], 5)["why"] == "손절"


def test_end_of_week_close():
    bars = [b(f"2026-11-2{i}", 100, 102, 98, 101) for i in range(3, 8)]
    r = simulate(R, bars, 5, "2026-11-27")
    assert r["why"] == "기간 종료" and r["ret"] == 1.0 and r["done"]


def test_cum():
    assert round(_cum([10, -10]), 4) == 0.99
