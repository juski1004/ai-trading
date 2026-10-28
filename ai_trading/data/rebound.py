"""바닥 반등 신호: 크게 떨어진 뒤 바닥을 다지고 돌아서는 종목 찾기. 2026-10-29 사용자 요청
("하락 후 아래꼬리, 거래량 상승, 바닥 골든크로스, 기관·외국인 매집 흔적 같은 걸 잡아서 보여 줘").

신호 6개 (모두 일봉 종가 기준, 숫자는 화면에 그대로 보여 줌):
  1 하락      최근 40거래일 고점 대비 저점이 -10% 이하, 그 저점이 최근 15거래일 안
  2 아래꼬리  저점 이후 최근 10거래일 안에 아래꼬리가 몸통의 2배 이상이고 하루 범위의 절반 이상인 날
  3 거래량    최근 5일 평균 거래량 ≥ 그 전 20일 평균 × 1.3
  4 골든크로스 최근 10거래일 안에 MACD가 시그널을 위로 뚫음, 뚫을 때 MACD가 0 아래(바닥권)
  5 수급      최근 5거래일 외국인+기관 순매수 합(주) > 0, 그중 3일 이상 순매수
  6 반등      현재가가 저점 대비 +3~20%이고 5일선 위 (20% 넘게 올랐으면 '늦었을 수 있음'으로 표시)
'하락'은 꼭 있어야 하고, 나머지 5개 중 3개 이상이면 목록에 올린다 (점수 = 맞은 신호 수).
결과: data/rebound.json {date, items:[{sym,name,code,price,chg,score,checks:{...},low,low_date,drop}]}
투자 권유가 아니라 차트·수급 조건을 기계적으로 걸러 낸 참고 목록.
"""
from __future__ import annotations

import pandas as pd


def _macd(c: pd.Series):
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    return m, m.ewm(span=9, adjust=False).mean()


def check(st: dict, dates: list[str], flows: list[dict] | None) -> dict | None:
    o, h, l, c, v = (pd.Series(st[k], dtype=float) for k in ("o", "h", "l", "c", "v"))
    n = len(c)
    if n < 60:
        return None
    win = c.iloc[-40:]
    hi_i = int(win.idxmax())
    lo_i = int(l.iloc[hi_i:].idxmin()) if hi_i < n - 1 else n - 1
    low = float(l.iloc[lo_i]); drop = (low / float(h.iloc[hi_i]) - 1) * 100
    ok_drop = drop <= -10 and lo_i >= n - 15
    if not ok_drop:
        return None
    ck: dict[str, dict] = {"drop": {"ok": True, "text": f"고점 {h.iloc[hi_i]:,.0f} → 저점 {low:,.0f} ({drop:.1f}%)"}}

    tail_day = None
    for i in range(max(lo_i - 2, n - 10), n):
        body = abs(c.iloc[i] - o.iloc[i]); rng = h.iloc[i] - l.iloc[i]; tail = min(o.iloc[i], c.iloc[i]) - l.iloc[i]
        if rng > 0 and tail >= 2 * max(body, rng * 0.05) and tail >= 0.5 * rng:
            tail_day = i
    ck["tail"] = {"ok": tail_day is not None,
                  "text": f"{dates[tail_day][5:].replace('-', '.')} 긴 아래꼬리 (저가 {l.iloc[tail_day]:,.0f})" if tail_day is not None else "긴 아래꼬리 없음"}

    v5, v20 = v.iloc[-5:].mean(), v.iloc[-25:-5].mean()
    r = v5 / v20 if v20 else 0
    ck["volume"] = {"ok": bool(r >= 1.3), "text": f"최근 5일 거래량 평소의 {r:.1f}배"}

    m, s = _macd(c)
    gc = None
    for i in range(n - 10, n):
        if m.iloc[i - 1] <= s.iloc[i - 1] and m.iloc[i] > s.iloc[i] and m.iloc[i] < 0:
            gc = i
    ck["macd"] = {"ok": gc is not None,
                  "text": f"{dates[gc][5:].replace('-', '.')} MACD 바닥권 골든크로스" if gc is not None else
                  ("MACD 시그널 위 (0 아래)" if m.iloc[-1] > s.iloc[-1] and m.iloc[-1] < 0 else "MACD 골든크로스 없음")}

    f5 = (flows or [])[-5:]
    if f5:
        tot = sum(x["frg"] + x["org"] for x in f5); days = sum(1 for x in f5 if x["frg"] + x["org"] > 0)
        frg = sum(x["frg"] for x in f5); org = sum(x["org"] for x in f5)
        ck["flow"] = {"ok": bool(tot > 0 and days >= 3), "text": f"5일 외국인 {frg:+,.0f}주 · 기관 {org:+,.0f}주 (순매수 {days}일)"}
    else:
        ck["flow"] = {"ok": False, "text": "수급 자료 없음"}

    up = (c.iloc[-1] / low - 1) * 100; ma5 = c.iloc[-5:].mean()
    late = up > 20
    ck["rebound"] = {"ok": bool(3 <= up <= 20 and c.iloc[-1] > ma5),
                     "text": f"저점 대비 {up:+.1f}%" + (" · 이미 많이 올라 늦었을 수 있음" if late else f" · 5일선 {'위' if c.iloc[-1] > ma5 else '아래'}")}

    score = sum(1 for k, x in ck.items() if k != "drop" and x["ok"])
    if score < 3:
        return None
    return {"sym": st["sym"], "name": st["name"], "code": st["code"], "price": round(float(c.iloc[-1])),
            "chg": round((c.iloc[-1] / c.iloc[-2] - 1) * 100, 2), "score": score, "low": round(low),
            "low_date": dates[lo_i], "drop": round(drop, 1), "checks": ck}


def build(stocks: dict, dates: list[str], flows_by_code: dict) -> dict:
    items = []
    for s, st in stocks.items():
        try:
            r = check({**st, "sym": s}, dates[-len(st["c"]):], flows_by_code.get(st["code"]))
        except Exception as e:  # 한 종목이 이상해도 나머지는 계속
            print(f"[반등 신호 {s}] {type(e).__name__}: {e}")
            r = None
        if r:
            items.append(r)
    items.sort(key=lambda x: (-x["score"], x["drop"]))
    return {"date": dates[-1], "items": items[:12]}
