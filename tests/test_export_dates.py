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
