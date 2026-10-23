import pandas as pd

from ai_trading.data.export import day_index


def test_day_index_matches_tz_aware_and_naive():
    naive = pd.DatetimeIndex(["2026-10-20", "2026-10-21"]).astype("datetime64[s]")
    aware = pd.DatetimeIndex(["2026-10-20 00:00", "2026-10-21 00:00"]).tz_localize("Asia/Seoul")
    assert day_index(naive).equals(day_index(aware))
    s = pd.Series([1.0, 2.0], index=aware)
    assert s.set_axis(day_index(s.index)).reindex(day_index(naive)).tolist() == [1.0, 2.0]


def test_day_index_drops_time_of_day():
    idx = pd.DatetimeIndex(["2026-10-21 15:30"]).tz_localize("UTC")
    assert str(day_index(idx)[0].date()) == "2026-10-21"


def test_axis_keeps_day_missing_from_kospi():
    from ai_trading.data.export import trading_axis
    kospi = pd.DatetimeIndex(["2026-10-20", "2026-10-21", "2026-10-23"]).tz_localize("Asia/Seoul")
    full = pd.DatetimeIndex(["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"])
    odd = pd.DatetimeIndex(["2026-10-21", "2026-10-24"])  # 한 종목에만 있는 날은 넣지 않음
    ax = trading_axis(kospi, [full, full, odd])
    assert [str(d.date()) for d in ax] == ["2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
    assert trading_axis(kospi, []).equals(day_index(kospi))


def test_drops_today_only_during_market_hours():
    from ai_trading.data.export import drop_unfinished_day
    ax = pd.DatetimeIndex(["2026-10-22", "2026-10-23"])
    assert len(drop_unfinished_day(ax, pd.Timestamp("2026-10-23 09:30", tz="Asia/Seoul"))) == 1
    assert len(drop_unfinished_day(ax, pd.Timestamp("2026-10-23 16:20", tz="Asia/Seoul"))) == 2
    assert len(drop_unfinished_day(ax, pd.Timestamp("2026-10-24 09:30", tz="Asia/Seoul"))) == 2
