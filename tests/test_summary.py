from datetime import date

from ai_trading.data.summary import recent_items, summarize


class FakeLLM:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def ask_json(self, prompt):
        self.prompts.append(prompt)
        return self.answer


TODAY = date(2026, 10, 22)
NEWS = {
    "A.KS": [{"date": "2026-10-21", "title": "A 실적 개선"}, {"date": "2026-10-20", "title": "A 신제품"},
             {"date": "2026-10-20", "title": "A 신제품"}, {"date": "2026-09-01", "title": "오래된 소식"}],
    "B.KS": [{"date": "2026-10-21", "title": "B 소식"}],
    "C.KS": [{"date": "2026-08-01", "title": "C 옛날"}],
}


def test_recent_items_dedup_and_window():
    r = recent_items(NEWS["A.KS"], TODAY, 7)
    assert [x["title"] for x in r] == ["A 실적 개선", "A 신제품"]


def test_summarize_orders_by_news_and_caps():
    llm = FakeLLM({"lines": ["한 줄", "두 줄", "세 줄", "네 줄"], "tone": "호재"})
    out = summarize(NEWS, {"A.KS": "에이"}, llm, TODAY, max_stocks=1)
    assert list(out) == ["A.KS"] and len(llm.prompts) == 1
    assert out["A.KS"]["lines"] == ["한 줄", "두 줄", "세 줄"] and out["A.KS"]["tone"] == "호재"
    assert "에이" in llm.prompts[0] and "오래된 소식" not in llm.prompts[0]


def test_summarize_skips_bad_answers_and_no_key():
    assert summarize(NEWS, {}, None, TODAY) == {}
    assert summarize(NEWS, {}, FakeLLM(None), TODAY) == {}
    out = summarize(NEWS, {}, FakeLLM({"lines": ["x"], "tone": "대박"}), TODAY)
    assert out["A.KS"]["tone"] == "중립"


def test_stops_at_time_budget():
    from datetime import date
    from ai_trading.data import summary

    class Slow:
        n = 0
        def ask_json(self, p):
            Slow.n += 1
            return {"lines": ["a"], "tone": "중립"}

    news = {f"S{i}": [{"date": "2026-10-22", "title": f"t{i}"}] for i in range(5)}
    out = summary.summarize(news, {}, Slow(), today=date(2026, 10, 22), budget_sec=-1)
    assert out == {} and Slow.n == 0
    out = summary.summarize(news, {}, Slow(), today=date(2026, 10, 22))
    assert len(out) == 5
