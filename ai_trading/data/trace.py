"""큰손 매수 흔적 (◆ 표시) — 2026-11-03 사용자: 참고 영상(세력 흔적 스캔·매집 각인)처럼 차트에 흔적을 찍고, 시장에서 흔적 난 종목 찾기.

그날 거래가 평소와 확 다를 때만 ◆ 를 찍는다 (네 가지 모두 맞아야 함).
  ① 규모: 거래량이 직전 60거래일 중앙값의 2배 이상
  ② 희소성: 직전 60거래일 중 가장 많은 쪽 5% 안 (최근 두세 달에 몇 번 없는 거래)
  ③ 방향: 오르며 끝남(전날보다 상승, 그날 범위의 위쪽 절반에서 마감) + 기관·외국인 합계 순매수(수급 자료가 있는 날만 확인)
  ④ 자리: 직전 20거래일이 옆걸음(고저 폭 15% 미만)이던 때 — 이미 급등한 뒤의 대량 거래는 제외
     (11/3 시험: ①~③만 쓰면 ◆ 뒤 20일 성적이 아무 날보다 나빴음(오른 비율 40% vs 48%). 옆걸음 자리만 고르면 54%·평균 +6% 로 뒤집힘)
영상과 달리 잘 오른 종목만 골라 보여 주지 않는다: 지난 ◆ 전체의 20거래일 뒤 결과(오른 비율·평균)를
아무 날이나 샀을 때(기준선)와 나란히 둔다. 투자 권유가 아니라 공개 시세·수급으로 계산한 참고 정보.
결과: data/trace.json {date, rule, stats, items:{sym:{marks,first,...}}, recent:[...]}
"""
from __future__ import annotations

from statistics import median

LOOK = 60       # 평소를 재는 기간 (거래일)
WINDOW = 60     # 차트에 보여 줄 흔적 탐색 기간
RECENT = 5      # '최근 흔적' 목록: 마지막 5거래일 안
AHEAD = 20      # 성적표: ◆ 뒤 20거래일


def marks_of(o: list, h: list, l: list, c: list, v: list, flow_by_idx: dict | None = None) -> list[dict]:
    """◆ 찍힌 날 목록 [{i, vr(평소 대비 배수)}]. flow_by_idx: 봉 위치 → 기관+외국인 순매수(주), 없으면 수급 조건 생략"""
    out = []
    for k in range(LOOK, len(c)):
        base = v[k - LOOK:k]
        med = median(base)
        if not med or not v[k]:
            continue
        vr = v[k] / med
        top5 = sorted(base)[int(len(base) * 0.95)]
        rng = h[k] - l[k]
        up = c[k] > c[k - 1] and (rng <= 0 or (c[k] - l[k]) / rng >= 0.5)
        big = flow_by_idx.get(k) if flow_by_idx else None
        box = (max(h[k - 20:k]) - min(l[k - 20:k])) / c[k] if c[k] else 1
        if vr >= 2 and v[k] >= top5 and up and box < 0.15 and (big is None or big > 0):
            out.append({"i": k, "vr": round(vr, 1)})
    return out


def build(stocks: dict, dates: list[str], flows_by_code: dict) -> dict:
    items, recent, fwd_sig, fwd_all = {}, [], [], []
    for s, st in stocks.items():
        try:
            c, v = st["c"], st["v"]
            o, h, l = st.get("o", c), st.get("h", c), st.get("l", c)
            ds = dates[-len(c):]
            pos = {d: k for k, d in enumerate(ds)}
            fl = {pos[x["date"]]: x["frg"] + x["org"] for x in (flows_by_code.get(st["code"]) or []) if x.get("date") in pos}
            mk = marks_of(o, h, l, c, v, fl)
            n = len(c)
            # 성적표: 모든 ◆ 와 모든 날(기준선)의 20거래일 뒤 수익
            for m in mk:
                if m["i"] + AHEAD < n:
                    fwd_sig.append(c[m["i"] + AHEAD] / c[m["i"]] - 1)
            for k in range(LOOK, n - AHEAD):
                fwd_all.append(c[k + AHEAD] / c[k] - 1)
            win = [m for m in mk if m["i"] >= n - WINDOW]
            if not win:
                continue
            f = win[0]["i"]
            hi = max(h[f:]) if h else max(c[f:])
            it = {"name": st["name"],
                  "marks": [{"d": ds[m["i"]], "n": j + 1, "vr": m["vr"], "c": round(c[m["i"]])} for j, m in enumerate(win)],
                  "first": ds[f], "first_c": round(c[f]),
                  "max_up": round((hi / c[f] - 1) * 100, 1), "now_up": round((c[-1] / c[f] - 1) * 100, 1),
                  "price": round(c[-1]),
                  # 앱 차트용 최근 60거래일 종가·거래량 (◆ 는 marks 의 날짜로 찍음)
                  "bars": {"d": ds[-WINDOW:], "c": [round(x) for x in c[-WINDOW:]], "v": [int(x) for x in v[-WINDOW:]]}}
            items[s] = it
            last = win[-1]["i"]
            if last >= n - RECENT:
                recent.append({"sym": s, "name": st["name"], "count": len(win), "last": ds[last], "vr": win[-1]["vr"],
                               "price": round(c[-1]), "chg": round((c[-1] / c[-2] - 1) * 100, 2), "now_up": it["now_up"]})
        except Exception as e:  # 한 종목이 이상해도 나머지는 계속
            print(f"[큰손 흔적 {s}] {type(e).__name__}: {e}")
    recent.sort(key=lambda x: (-x["count"], -x["vr"]))

    def summ(xs: list[float]) -> dict | None:
        if not xs:
            return None
        xs = sorted(xs)
        return {"n": len(xs), "win": round(sum(1 for x in xs if x > 0) / len(xs) * 100, 1),
                "avg": round(sum(xs) / len(xs) * 100, 2), "med": round(xs[len(xs) // 2] * 100, 2)}

    return {"date": dates[-1], "ahead": AHEAD,
            "rule": "옆걸음(20일 고저 폭 15% 미만)하던 종목에서 거래량이 평소(60일 중앙값)의 2배 이상 + 최근 60일 상위 5% + 오르며 마감 + 기관·외국인 순매수",
            "stats": {"signal": summ(fwd_sig), "base": summ(fwd_all)},
            "items": items, "recent": recent[:15]}
