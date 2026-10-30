from ai_trading.data.cards import HOSTS, THEMES, host_of, theme_of


def test_host_changes_every_day():
    assert host_of("2026-10-26")[0] == "joy"          # 월
    assert host_of("2026-10-27")[0] == "egen"         # 다음 날은 다음 사람
    assert host_of("2026-10-30")[0] == "ray"          # 금
    assert host_of("2026-10-26", 1)[0] == "egen"      # 다음 날 진행자
    assert host_of("2026-10-25")[0] == "lloyd"        # 기준일 이전도 순서 유지
    assert host_of("2026-11-06")[0] == "joy"          # 11일 돌고 다시 처음


def test_eleven_hosts_with_men_and_directors():
    ids = [h[0] for h in HOSTS]
    assert len(ids) == 11 and len(set(ids)) == 11
    assert {"egen", "teto", "puppy", "theo", "seunghyun"} <= set(ids)


def test_theme_changes_weekly_no_purple():
    assert theme_of("2026-10-26") is theme_of("2026-10-30")
    assert theme_of("2026-10-26") is not theme_of("2026-11-02")
    for t in THEMES:
        r, g, b = t["paper"]; assert not (b > g + 8 and r > g)   # 보라 바탕 없음


def test_weekend_term_dates():
    from ai_trading.data.termcards import weekend_dates
    assert weekend_dates("2026-10-30") == ["2026-10-31", "2026-11-01"]   # 금 → 그 주 토·일
    assert weekend_dates("2026-10-29") == ["2026-10-31", "2026-11-01"]   # 금요일 휴장이면 목 데이터로
    assert weekend_dates("2026-10-27") == []
