from ai_trading.data.cards import HOSTS, host_of


def test_host_rotates_one_per_weekday():
    assert host_of("2026-10-26")[0] == "joy"          # 월
    assert host_of("2026-10-27")[0] == "oscar"        # 화
    assert host_of("2026-10-30")[0] == "lloyd"        # 금
    assert host_of("2026-11-02")[0] == "nova"         # 다음 주 월 (주말은 안 셈)
    assert host_of("2026-11-03")[0] == "joy"          # 6명 돌고 다시 처음
    assert host_of("2026-10-23")[0] == "nova"         # 기준일 이전도 순서 유지
    assert host_of("2026-10-26", 1)[0] == "oscar"


def test_no_director_in_hosts():
    ids = [h[0] for h in HOSTS]
    assert len(ids) == 6 and "theo" not in ids and "seunghyun" not in ids
