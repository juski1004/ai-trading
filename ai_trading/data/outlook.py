"""오늘의 시장 전망: 지수·경제지표·수급·뉴스를 모아 AI(Gemini)가 짧게 쓴다. 키가 없거나 실패하면 규칙 문장."""
from __future__ import annotations

import pandas as pd


def _chg(s: pd.Series | None, n: int) -> float | None:
    if s is None or len(s) <= n:
        return None
    return float((s.iloc[-1] / s.iloc[-1 - n] - 1) * 100)


def facts(daily: dict, mflows: dict, big_flow: dict | None, eco_news: list[dict], breadth: dict) -> dict:
    g = lambda k, n: _chg(daily.get(k), n)
    f = {
        "코스피": {"1일": g("kospi", 1), "5일": g("kospi", 5), "20일": g("kospi", 20)},
        "코스닥": {"1일": g("kosdaq", 1), "5일": g("kosdaq", 5), "20일": g("kosdaq", 20)},
        "원달러_20일%": g("usdkrw", 20), "WTI_20일%": g("wti", 20),
        "미국10년물": None if daily.get("us10y") is None else round(float(daily["us10y"].iloc[-1]), 2),
        "VIX": None if daily.get("vix") is None else round(float(daily["vix"].iloc[-1]), 1),
        "오늘_시장수급_억원": mflows, "대형주_수급_5일": big_flow, "대형주_20일선_위_비율": breadth,
        "주요_뉴스": [x["title"] for x in eco_news[:8]],
    }
    return _round(f)


def _round(v):
    """안쪽(코스피 1일 등)까지 소수 둘째 자리로 — AI가 0.29870748…% 처럼 그대로 옮겨 쓰지 않게"""
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def tidy(t: str) -> str:
    """문장 속 긴 소수(0.2987…)는 둘째 자리로, '9860.0억'은 '9,860억'으로"""
    import re

    t = re.sub(r"(\d+)\.0(억|조)", r"\1\2", t)
    t = re.sub(r"\d+\.\d{3,}", lambda m: f"{float(m.group()):.2f}", t)
    return re.sub(r"(?<![\d.,])(\d{4,})(?=\s?(억|조|만|원))", lambda m: f"{int(m.group(1)):,}", t)


def rule_text(f: dict) -> dict:
    k = f["코스피"]
    tone = "긍정" if (k["5일"] or 0) > 1 and (k["20일"] or 0) > 0 else "부정" if (k["5일"] or 0) < -1 and (k["20일"] or 0) < 0 else "중립"
    lines = [f"코스피는 5일 {k['5일'] or 0:+.1f}%, 20일 {k['20일'] or 0:+.1f}% 움직였습니다."]
    m = f.get("오늘_시장수급_억원", {}).get("KOSPI")
    if m:
        lines.append(f"오늘 코스피 외국인 {m['frg']:+,.0f}억 원, 기관 {m['org']:+,.0f}억 원, 개인 {m['ind']:+,.0f}억 원 순매수했습니다.")
    if f.get("원달러_20일%") is not None:
        lines.append(f"원/달러는 20일 {f['원달러_20일%']:+.1f}%, 유가는 {f.get('WTI_20일%') or 0:+.1f}%, VIX는 {f.get('VIX')}입니다.")
    return {"tone": tone, "headline": "지수·수급·경제지표 요약 (자동 문장)", "lines": lines, "watch": [], "source": "규칙"}


PROMPT = """너는 한국 증권사 리서치센터의 시황 담당이다. 아래 사실만 근거로 '오늘의 시장 전망'을 써라.
없는 사실을 지어내지 말고, 투자 권유 표현(사라/팔아라/수익 보장)은 쓰지 마라.
초보 투자자도 바로 이해하게 쉬운 말로, 각 줄은 한 문장 40자 안팎으로 짧게, 모든 문장을 '~습니다/~입니다' 존댓말로 끝내라('~이다/~한다' 금지).
퍼센트는 소수 둘째 자리까지만(예: +0.30%), 금액은 '9,860억 원'처럼 쉼표를 넣어라. 괄호 속 숫자 나열은 하지 마라.

사실(JSON): {facts}

JSON으로만 답하라:
{{"tone":"긍정|중립|부정","headline":"한 줄 제목(25자 이내)","lines":["오늘 시장 요약","수급 해석","환율·금리·유가 영향","내일 이후 전망과 근거"],"watch":["앞으로 지켜볼 것 2~3개"]}}"""


def write(daily: dict, mflows: dict, big_flow: dict | None, eco_news: list[dict], breadth: dict) -> dict:
    import json

    from ..llm import from_env

    f = facts(daily, mflows, big_flow, eco_news, breadth)
    llm = from_env()
    if llm is not None:
        ans = llm.ask_json(PROMPT.format(facts=json.dumps(f, ensure_ascii=False)))
        if isinstance(ans, dict) and ans.get("lines"):
            return {"tone": str(ans.get("tone", "중립"))[:4], "headline": str(ans.get("headline", ""))[:60],
                    "lines": [tidy(str(x))[:220] for x in ans["lines"]][:5], "watch": [str(x)[:80] for x in ans.get("watch", [])][:4],
                    "source": "AI", "engine": getattr(llm, "last_used", None) or "Gemini", "facts": f}
    out = rule_text(f)
    out["facts"] = f
    return out
