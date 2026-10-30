from ai_trading.data.position import avg_cost, build, verdict


def test_avg_cost_buy_then_partial_sell_keeps_average():
    a, inv = avg_cost([(100, 1000), (100, 2000), (-100, 3000)])
    assert inv == 100 and round(a) == 1500  # 판 물량은 평단으로 빠지고 남은 평단 유지


def test_avg_cost_none_when_sold_out():
    a, inv = avg_cost([(100, 1000), (-100, 1200)])
    assert a is None


def test_verdict_bands():
    assert "근처" in verdict(1) and "위" in verdict(5) and "아래" in verdict(-5)


def test_build_tracker_needs_streak_and_volume():
    dates = [f"2026-09-{d:02d}" for d in range(1, 31)]
    c = [1000 + i for i in range(30)]
    v = [100] * 25 + [200] * 5
    fl = [{"date": d, "frg": 0, "org": (-10 if i < 25 else 50)} for i, d in enumerate(dates)]
    st = {"A.KS": {"code": "A", "name": "테스트", "c": c, "v": v}}
    r = build(st, dates, {"A": fl})
    assert r["tracker"] and r["tracker"][0]["streak"] == 5 and r["items"]["A.KS"]["basis"] == "기관·외국인"
