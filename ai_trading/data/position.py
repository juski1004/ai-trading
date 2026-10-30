"""기관 매수 트래커 + 위치 진단 (2026-10-31 사용자: 참고 릴스(onetop_economy)에서 쓸 만한 것 가져오기).

1) 위치 진단: 최근 약 3개월 기관·외국인 순매수(주)를 그날 종가로 쌓아 '추정 평균 단가'를 만들고,
   지금 주가가 그 평단보다 위인지 아래인지 보여 준다. 팔면 평균 단가로 줄인다(남은 물량의 평단 유지).
   - 실제 매매 가격·기간 시작 전 보유분은 알 수 없어 추정치. 화면에 그렇게 적는다.
2) 기관 매수 트래커: 기관이 오늘까지 연속 순매수한 날 수(3일 이상)와 최근 5일 거래량 배수(1.3배 이상)가
   함께 나온 종목. 연속일 수·순매수 금액 순.
결과: data/position.json {date, items:{sym:{...}}, tracker:[...]}
투자 권유가 아니라 공개 수급·시세로 계산한 참고 정보.
"""
from __future__ import annotations


def avg_cost(rows: list[tuple[float, float]]) -> tuple[float | None, float]:
    """rows: [(순매수 주식 수, 그날 종가)] 시간순 → (남은 물량의 추정 평단, 남은 물량). 남은 게 없으면 (None, 0)."""
    inv = cost = bought = 0.0
    for q, p in rows:
        if not p:
            continue
        if q > 0:
            inv += q; cost += q * p; bought += q
        elif q < 0 and inv > 0:
            sell = min(-q, inv); cost -= cost / inv * sell; inv -= sell
    if inv <= 0 or inv < bought * 0.1:  # 거의 다 팔아 남은 게 적으면 평단 의미 없음
        return None, max(inv, 0.0)
    return cost / inv, inv


def verdict(gap: float) -> str:
    if gap >= 15: return "기관·외국인 평단보다 많이 위 — 이미 수익이 커서 차익 매물이 나올 수 있는 자리"
    if gap >= 3: return "기관·외국인 평단 위 — 큰손들이 수익 중인 자리"
    if gap > -3: return "기관·외국인 평단 근처 — 큰손들의 본전 자리라 지지·저항을 확인하는 구간"
    if gap > -15: return "기관·외국인 평단 아래 — 큰손들도 손실 중인 자리"
    return "기관·외국인 평단보다 많이 아래 — 큰손들도 크게 손실 중인 자리"


def build(stocks: dict, dates: list[str], flows_by_code: dict) -> dict:
    items, tracker = {}, []
    for s, st in stocks.items():
        try:
            fl = flows_by_code.get(st["code"]) or []
            if len(fl) < 20:
                continue
            ds = dates[-len(st["c"]):]; close = dict(zip(ds, st["c"])); price = float(st["c"][-1])
            rows_big = [(x["frg"] + x["org"], close.get(x["date"])) for x in fl]
            avg, inv = avg_cost(rows_big)
            org_avg, _ = avg_cost([(x["org"], close.get(x["date"])) for x in fl])
            it = {"name": st["name"], "price": round(price), "days": len(fl), "from": fl[0]["date"]}
            basis = "기관·외국인"
            if not avg and org_avg:  # 둘을 합치면 남은 물량이 적은 종목은 기관만으로
                avg, basis = org_avg, "기관"
            if avg:
                gap = (price / avg - 1) * 100
                it.update({"avg": round(avg), "gap": round(gap, 1), "basis": basis,
                           "verdict": verdict(gap).replace("기관·외국인", basis)})
            if org_avg:
                it["org_avg"] = round(org_avg); it["org_gap"] = round((price / org_avg - 1) * 100, 1)
            # 기관 연속 순매수 (오늘부터 거꾸로)
            streak = 0
            for x in reversed(fl):
                if x["org"] > 0: streak += 1
                else: break
            v = st["v"]; v5 = sum(v[-5:]) / 5; v20 = sum(v[-25:-5]) / 20 if len(v) >= 25 else 0
            vr = v5 / v20 if v20 else 0
            amt = sum(x["org"] * (close.get(x["date"]) or price) for x in fl[-streak:]) if streak else 0
            it.update({"org_streak": streak, "vol_ratio": round(vr, 2), "org_amt": round(amt / 1e8)})
            items[s] = it
            if streak >= 3 and vr >= 1.3 and amt > 0:
                tracker.append({"sym": s, "name": st["name"], "price": round(price),
                                "chg": round((st["c"][-1] / st["c"][-2] - 1) * 100, 2),
                                "streak": streak, "amt": round(amt / 1e8), "vol_ratio": round(vr, 2),
                                "gap": it.get("gap")})
        except Exception as e:  # 한 종목이 이상해도 나머지는 계속
            print(f"[위치 진단 {s}] {type(e).__name__}: {e}")
    tracker.sort(key=lambda x: (-x["streak"], -x["amt"]))
    return {"date": dates[-1], "items": items, "tracker": tracker[:10]}
