from ai_trading.data.cards import HOSTS, THEMES, host_of, theme_of


def test_host_changes_once_a_week():
    assert host_of("2026-10-26")[0] == "joy"          # 월
    assert host_of("2026-10-30")[0] == "joy"          # 같은 주 금요일도 같은 사람
    assert host_of("2026-11-02")[0] == "egen"         # 다음 주 월
    assert host_of("2026-10-26", 1)[0] == "egen"      # '다음 주는' 안내
    assert host_of("2026-10-23")[0] == "lloyd"        # 기준 주 이전도 순서 유지
    assert host_of("2027-01-11")[0] == "joy"          # 11주 돌고 다시 처음


def test_eleven_hosts_with_men_and_directors():
    ids = [h[0] for h in HOSTS]
    assert len(ids) == 11 and len(set(ids)) == 11
    assert {"egen", "teto", "puppy", "theo", "seunghyun"} <= set(ids)


def test_theme_changes_weekly_no_purple():
    assert theme_of("2026-10-26") is theme_of("2026-10-30")
    assert theme_of("2026-10-26") is not theme_of("2026-11-02")
    for t in THEMES:
        r, g, b = t["paper"]; assert not (b > g + 8 and r > g)   # 보라 바탕 없음
