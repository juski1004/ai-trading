import json

from ai_trading.data.pick import build_pick, candidates


def stock(name, score, tech, fin, risk="보통", chg=0.5, miles=0.5):
    return {"name": name, "code": name, "market": "KOSPI", "price": 10000, "chg": chg, "score": score, "label": "긍정",
            "tech_score": tech, "fin_score": fin, "tech": [["MA", 1, "B"], ["RSI", 50, "N"]], "fin": {"roe": 12.0, "per": 9.0},
            "risk": {"level": risk, "vol": 2.0, "reasons": ["이상 없음"]}, "target": 11000, "stop": 9500, "news": [], "closes": [1, 2],
            "opinions": [{"agent": a, "score": miles if a == "MILES" else 0.3, "summary": "의견, 최대 1주"} for a in ("JOY", "OSCAR", "RAY", "MILES")]}


def write(tmp, stocks, **extra):
    (tmp / "scores.json").write_text(json.dumps({"date": "2026-10-23", "stocks": stocks}, ensure_ascii=False))
    for k, v in extra.items():
        (tmp / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False))


class FakeLLM:
    def __init__(self, ans):
        self.ans, self.prompts = ans, []

    def ask_json(self, p):
        self.prompts.append(p)
        return self.ans


def test_candidates_filters_unsafe():
    sc = {"stocks": {"A": stock("A", 0.4, 4, 4), "LOWTECH": stock("B", 0.6, 2, 4), "RISKY": stock("C", 0.6, 4, 4, risk="높음"),
                     "CHASE": stock("D", 0.6, 4, 4, miles=-0.5), "JUMP": stock("E", 0.6, 4, 4, chg=12), "WEAKFIN": stock("F", 0.6, 4, 1.0),
                     "NOFIN": stock("G", 0.35, 4, None)}}
    assert [s for _, s in candidates(sc)] == ["A", "NOFIN"]


def test_no_pick_when_nothing_qualifies(tmp_path):
    write(tmp_path, {"X": stock("X", 0.1, 4, 4)})
    p = build_pick(tmp_path)
    assert p["found"] is False and "쉬어" in p["reason"]


def test_pick_report_with_ai_and_fallback(tmp_path):
    write(tmp_path, {"A": stock("에이", 0.5, 4, 4), "B": stock("비", 0.35, 3.2, 3.5)},
          fin={"A": {"est": {"target": {"mean": 13000}, "eps": [{"period": "올해", "avg": 1000, "growth": 0.2, "n": 5}]}}},
          outlook={"tone": "부정", "headline": "시장 약세", "lines": ["코스피 하락"]})
    llm = FakeLLM({"opinion": "분할로 들어가세요. 참고 의견입니다."})
    p = build_pick(tmp_path, llm)
    assert p["found"] and p["name"] == "에이" and p["director"]["source"] == "AI"
    assert p["regime"] == "하락기" and any("목표주가" in x for x in p["reasons"])
    assert p["reporter"]["name"] and all("최대" not in x["say"] for x in p["staff"])
    assert "에이" in llm.prompts[0]
    p2 = build_pick(tmp_path, FakeLLM(None))
    assert p2["director"]["source"] == "규칙" and "2종목 가운데" in p2["director"]["opinion"]
    assert p2["reporter"] == p["reporter"]  # 같은 날은 같은 직원이 보고
