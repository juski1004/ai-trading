import json
from pathlib import Path

from ai_trading.data import quiz
from ai_trading.data.hashtags import overlaps


def _market(n=200):
    import math
    dates = [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    st = {}
    for j in range(3):
        c = [10000 * (1 + 0.3 * math.sin(i / (9 + j))) for i in range(n)]
        st[f"00{j}.KS"] = {"sym": f"00{j}.KS", "name": f"회사{j}", "o": c, "h": [x * 1.01 for x in c], "l": [x * 0.99 for x in c], "c": c, "v": [1000 + i for i in range(n)]}
    return {"dates": dates, "stocks": st}


def test_pick_is_past_and_stable():
    m = _market()
    a, b = quiz.pick(m, "2026-11-11"), quiz.pick(m, "2026-11-11")
    assert a == b and a is not None
    assert len(a["bars"]["c"]) == quiz.SHOW + quiz.AHEAD
    assert a["cut"] <= m["dates"][-26]          # 최근 25거래일은 안 씀
    assert 10 <= abs(a["chg"]) <= 40 and a["up"] == (a["chg"] > 0)


def test_tags_and_answer_due(tmp_path: Path):
    assert not overlaps(quiz.QUIZ_TAGS.split()) and len(quiz.QUIZ_TAGS.split()) == 8
    (tmp_path / "data" / "quiz").mkdir(parents=True)
    (tmp_path / "data" / "quiz" / "quiz.json").write_text(json.dumps({"answer_date": "2026-11-12"}))
    assert quiz.answer_due(tmp_path, "2026-11-12") and not quiz.answer_due(tmp_path, "2026-11-13")
