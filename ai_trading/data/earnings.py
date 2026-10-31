"""실적 발표가 다가온 종목과 '호재 전 진입' 판단 (앱 알림용 earnings.json).

발표일은 PC 화면 nextEarn 과 같은 방식: 아직 발표 안 한 분기의 공시일, 없으면 마지막 발표 분기 끝 + 3개월 + 30일.
증권사 예상(이번 분기 EPS 평균·전년 대비 증가율)과 최근 5일 주가를 정리한다. 데이터 요약이며 매매를 권하는 문장은 쓰지 않는다.
"""
from __future__ import annotations

from datetime import date, timedelta


def _next_date(quarters: list[dict], today: str) -> tuple[str, bool] | None:
    """(발표일, 추정 여부)"""
    for q in quarters:
        if q.get("date") and q["date"] > today:
            return q["date"], False
    done = [q for q in quarters if q.get("date") and q["date"] <= today and q.get("end")]
    if not done:
        return None
    y, m, d = (int(x) for x in done[-1]["end"].split("-"))
    m += 3
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return (date(y, m, min(d, 28)) + timedelta(days=30)).isoformat(), True


def build_earnings(stocks: dict, fin: dict, today: str, within_days: int = 14) -> dict:
    out = []
    for s, st in stocks.items():
        f = fin.get(s) or {}
        got = _next_date(f.get("quarters") or [], today)
        if not got:
            continue
        nd, guess = got
        days = (date.fromisoformat(nd) - date.fromisoformat(today)).days
        if not 0 <= days <= within_days or (guess and days <= 1):  # 추정일이 됐는데 공시가 없으면 날짜를 모르는 것 → 알리지 않음
            continue
        eps = next((x for x in (f.get("est") or {}).get("eps", []) if x.get("period") == "이번 분기"), None)
        g = eps.get("growth") if eps else None  # 전년 같은 분기 대비 (1.0 = +100%)
        c = st["c"]
        r5 = (c[-1] / c[-6] - 1) * 100 if len(c) >= 6 and c[-6] else 0.0
        if g is None:
            view, tone = "증권사 예상치가 없어요. 발표 결과가 나오면 다시 정리해요.", "중립"
        elif g >= 0.2 and r5 < 5:
            view, tone = f"증권사들은 EPS가 전년보다 {g * 100:+.0f}% 늘 것으로 예상해요. 최근 5일 주가는 {r5:+.1f}%예요.", "호재"
        elif g >= 0.2:
            view, tone = f"예상 EPS {g * 100:+.0f}%로 좋지만 최근 5일 {r5:+.1f}% 올라 기대가 이미 주가에 반영됐을 수 있어요.", "중립"
        elif g < 0:
            view, tone = f"증권사들은 EPS가 전년보다 {g * 100:+.0f}% 줄 것으로 예상해요. 발표 때 실망 매물이 나올 수 있어요.", "악재"
        else:
            view, tone = f"예상 EPS {g * 100:+.0f}%로 무난한 수준이에요. 최근 5일 주가는 {r5:+.1f}%예요.", "중립"
        out.append({"sym": s, "name": st["name"], "date": nd, "guess": guess, "days": days, "eps": round(eps["avg"]) if eps and eps.get("avg") else None,
                    "growth": round(g * 100, 1) if g is not None else None, "r5": round(r5, 2), "tone": tone, "view": view})
    out.sort(key=lambda x: x["days"])
    return {"date": today, "items": out}
