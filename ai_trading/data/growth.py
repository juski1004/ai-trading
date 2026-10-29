"""고성장 기업 발굴. 2026-10-29 사용자 요청("주식연구소에 종목 발굴 하나 넣자", 'GPT로 10배 주식 찾는 프롬프트' 카드 참고).
카드의 기준 중 우리 데이터로 확인할 수 있는 6가지를 숫자로 걸러 낸다 (시장 규모·점유율·고객 수는 자료가 없어 뺌).
  1 매출 성장 전망   증권사 예상 매출: 올해 +15% 이상, 내년 +10% 이상
  2 이익 성장        증권사 예상 주당순이익(EPS): 올해 +20% 이상, 내년 +15% 이상
  3 실적 매출 성장   최근 분기 매출이 1년 전 같은 분기보다 +15% 이상
  4 이익률 개선      최근 분기 영업이익률이 1년 전보다 높고, 직전 3분기 평균보다 높음
  5 증권사 시각      평균 목표가가 현재가보다 +15% 이상, 매수 의견 70% 이상
  6 성장 대비 가격   PEG(내년 예상 PER ÷ 내년 EPS 성장률%) 1.5 이하
5개 이상 맞으면 목록 (점수 = 맞은 수). 결과 data/growth.json. 투자 권유가 아니라 숫자 조건으로 거른 참고 목록.
"""
from __future__ import annotations


def _est(e: dict, kind: str, period: str):
    for x in (e or {}).get(kind, []) or []:
        if x.get("period") == period:
            return x
    return None


def check(sym: str, st: dict, f: dict, price: float) -> dict | None:
    e = (f or {}).get("est") or {}
    q = [x for x in (f or {}).get("quarters", []) if x.get("rev") and x.get("op") is not None]  # 은행·보험은 영업이익 칸이 없어 이 둘은 건너뜀
    ck = {}
    r1, r2 = _est(e, "rev", "올해"), _est(e, "rev", "내년")
    if r1 and r2 and r1.get("growth") is not None and r2.get("growth") is not None:
        ck["rev_est"] = {"ok": r1["growth"] >= 0.15 and r2["growth"] >= 0.10, "text": f"예상 매출 올해 {r1['growth']*100:+.0f}% · 내년 {r2['growth']*100:+.0f}%"}
    e1, e2 = _est(e, "eps", "올해"), _est(e, "eps", "내년")
    if e1 and e2 and e1.get("growth") is not None and e2.get("growth") is not None:
        ck["eps_est"] = {"ok": e1["growth"] >= 0.20 and e2["growth"] >= 0.15, "text": f"예상 주당순이익 올해 {e1['growth']*100:+.0f}% · 내년 {e2['growth']*100:+.0f}%"}
    if len(q) >= 5:
        g = q[-1]["rev"] / q[-5]["rev"] - 1
        ck["rev_yoy"] = {"ok": g >= 0.15, "text": f"최근 분기 매출 1년 전보다 {g*100:+.0f}%"}
        m = lambda x: x["op"] / x["rev"] * 100
        prev3 = sum(m(x) for x in q[-4:-1]) / 3
        ck["margin"] = {"ok": m(q[-1]) > m(q[-5]) and m(q[-1]) > prev3, "text": f"영업이익률 {m(q[-5]):.1f}% → {m(q[-1]):.1f}% (직전 3분기 평균 {prev3:.1f}%)"}
    t, rec = e.get("target") or {}, e.get("rec") or {}
    if t.get("mean") and price:
        up = (t["mean"] / price - 1) * 100; tot = sum(rec.values()) or 0
        buy = (rec.get("strongBuy", 0) + rec.get("buy", 0)) / tot * 100 if tot else 0
        ck["analyst"] = {"ok": up >= 15 and buy >= 70, "text": f"평균 목표가 {t['mean']:,.0f}원 ({up:+.0f}%) · 매수 의견 {buy:.0f}%"}
    if e2 and e2.get("avg") and e2.get("growth") and e2["growth"] > 0 and price:
        per = price / e2["avg"]; peg = per / (e2["growth"] * 100)
        ck["peg"] = {"ok": peg <= 1.5, "text": f"내년 예상 PER {per:.1f}배 · PEG {peg:.2f}"}
    if len(ck) < 5:
        return None
    score = sum(1 for x in ck.values() if x["ok"])
    if score < 5:
        return None
    return {"sym": sym, "name": st["name"], "code": st["code"], "price": round(price), "chg": st.get("chg", 0),
            "score": score, "n": len(ck), "checks": ck}


def build(scores: dict, fin: dict) -> dict:
    items = []
    for s, st in scores["stocks"].items():
        try:
            r = check(s, st, fin.get(s), st["price"])
        except Exception as ex:
            print(f"[고성장 {s}] {type(ex).__name__}: {ex}"); r = None
        if r:
            items.append(r)
    g = lambda x: float(x["checks"].get("rev_est", {}).get("text", "내년 +0%").split("내년 ")[-1].rstrip("%") or 0)
    items.sort(key=lambda x: (-x["score"], -g(x)))  # 맞은 수 → 내년 예상 매출 성장 큰 순
    return {"date": scores["date"], "items": items[:12]}
