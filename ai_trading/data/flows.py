"""수급: 외국인·기관·개인 순매수 (네이버 증권 모바일 화면이 쓰는 공개 주소).

공식 API가 아니라 언제든 바뀌거나 막힐 수 있다. 실패하면 빈 값을 돌려주고 나머지는 계속 돈다.
"""
from __future__ import annotations

import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (ai-trading paper game)"}


def _num(s) -> float:
    try:
        return float(str(s).replace(",", "").replace("%", "").replace("+", ""))
    except Exception:
        return 0.0


def _day(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def stock_flows(code: str, days: int = 60) -> list[dict]:
    """최근 거래일별 [{date, frg, org, ind (주), frg_ratio (%)}], 오래된 날짜부터."""
    try:
        rows = requests.get(f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize={days}", headers=UA, timeout=15).json()
    except Exception as e:
        print(f"[수급 {code} 실패] {type(e).__name__}: {str(e)[:80]}")
        return []
    out = [{"date": _day(r["bizdate"]), "frg": _num(r.get("foreignerPureBuyQuant")), "org": _num(r.get("organPureBuyQuant")),
            "ind": _num(r.get("individualPureBuyQuant")), "frg_ratio": _num(r.get("foreignerHoldRatio"))} for r in rows if r.get("bizdate")]
    return sorted(out, key=lambda x: x["date"])


def market_flows() -> dict:
    """오늘 코스피·코스닥 투자자별 순매수 (억 원)."""
    out = {}
    for k in ("KOSPI", "KOSDAQ"):
        try:
            r = requests.get(f"https://m.stock.naver.com/api/index/{k}/trend", headers=UA, timeout=15).json()
            out[k] = {"date": _day(r["bizdate"]), "ind": _num(r["personalValue"]), "frg": _num(r["foreignValue"]), "org": _num(r["institutionalValue"])}
        except Exception as e:
            print(f"[시장 수급 {k} 실패] {type(e).__name__}: {str(e)[:80]}")
    return out


def all_stock_flows(codes: list[str]) -> dict[str, list[dict]]:
    out = {}
    for c in codes:
        f = stock_flows(c)
        if f:
            out[c] = f
        time.sleep(0.15)
    return out


def flow_outlook(rows: list[dict], closes: list[float] | None = None) -> dict | None:
    """최근 흐름으로 본 수급 전망 (추정). 금액 = 수량 × 종가로 근사.

    외국인·기관의 5일·20일 순매수 방향과 연속일, 외국인 보유율 변화를 점수로 합친다.
    """
    if len(rows) < 10:
        return None
    px = closes or [1.0] * len(rows)
    px = px[-len(rows):] if len(px) >= len(rows) else [px[-1]] * len(rows)
    amt = lambda k, n: sum(r[k] * p for r, p in zip(rows[-n:], px[-n:]))

    def streak(k):
        s, sign = 0, 0
        for r in reversed(rows):
            v = 1 if r[k] > 0 else -1 if r[k] < 0 else 0
            if v == 0 or (sign and v != sign):
                break
            sign, s = v, s + 1
        return s * sign

    f5, f20, o5, o20 = amt("frg", 5), amt("frg", 20), amt("org", 5), amt("org", 20)
    dr = rows[-1]["frg_ratio"] - rows[-min(20, len(rows))]["frg_ratio"]
    sgn = lambda x: 1 if x > 0 else -1 if x < 0 else 0
    score = 0.35 * sgn(f5) + 0.2 * sgn(f20) + 0.25 * sgn(o5) + 0.1 * sgn(o20) + 0.1 * sgn(dr)
    fs, os_ = streak("frg"), streak("org")
    if fs >= 3 or fs <= -3:
        score += 0.1 * sgn(fs)
    score = max(-1.0, min(1.0, score))
    label = "매수 우위 지속 예상" if score >= 0.45 else "매수 우위 약함" if score >= 0.15 else \
        "매도 우위 지속 예상" if score <= -0.45 else "매도 우위 약함" if score <= -0.15 else "뚜렷한 방향 없음"
    return {"score": round(score, 2), "label": label, "frg5": round(f5), "frg20": round(f20), "org5": round(o5), "org20": round(o20),
            "frg_streak": fs, "org_streak": os_, "ratio_chg20": round(dr, 2)}
