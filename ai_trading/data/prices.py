"""거래 전용 시세: 시가총액 상위 코스피 200 + 코스닥 150 종목의 종가·등락률·거래 상태.

AI 분석(78종목)은 뉴스·재무까지 모아야 해서 종목을 늘리기 어렵지만, 모의투자에서 사고팔기만 하려면
종가와 거래 가능 여부면 충분하다. 네이버 모바일 증권의 시가총액 순위 API(요청 7번)로 받아 `prices.json`에 쓴다.
분석 대상이 아닌 종목은 앱에서 '거래 가능 · 분석 없음'으로 보인다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

NAVER = "https://m.stock.naver.com/api/stocks/marketValue/{mkt}?page={page}&pageSize=100"
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15", "Accept": "application/json"}
PLAN = {"KOSPI": 2, "KOSDAQ": 2}  # 페이지 수 (100개씩): 코스피 200, 코스닥 200 중 거래 가능한 것


def _num(x) -> float | None:
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse(rows: list[dict], market: str) -> dict:
    """네이버 응답 목록 → {sym: {...}}. ETF·우선주 등 종목이 아닌 것은 뺀다."""
    suffix = ".KS" if market == "KOSPI" else ".KQ"
    out = {}
    for r in rows:
        if r.get("stockEndType") != "stock":
            continue
        code = str(r.get("itemCode") or "").strip()
        price = _num(r.get("closePrice"))
        if len(code) != 6 or not price:
            continue
        stop = (r.get("tradeStopType") or {}).get("name", "TRADING")
        out[code + suffix] = {
            "name": r.get("stockName", code), "code": code, "market": market,
            "price": price, "chg": _num(r.get("fluctuationsRatio")) or 0.0,
            "vol": _num(r.get("accumulatedTradingVolume")) or 0.0,
            "cap": _num(r.get("marketValue")),  # 백만 원
            "halt": stop != "TRADING" or r.get("tradableStatus") not in (None, "tradable"),
            "at": (r.get("localTradedAt") or "")[:10],
        }
    return out


def fetch(session: requests.Session | None = None) -> dict:
    s = session or requests.Session()
    stocks: dict = {}
    for mkt, pages in PLAN.items():
        for page in range(1, pages + 1):
            r = s.get(NAVER.format(mkt=mkt, page=page), headers=UA, timeout=20)
            r.raise_for_status()
            stocks.update(parse(r.json().get("stocks", []), mkt))
            time.sleep(0.3)
    return stocks


def build(out: Path, analyzed: set[str] | None = None) -> dict:
    stocks = fetch()
    dates = sorted({v["at"] for v in stocks.values() if v["at"]})
    date = dates[-1] if dates else ""
    # 날짜가 다른(거래 정지 등으로 오래된) 종목은 거래 정지로 표시
    for v in stocks.values():
        if v["at"] and v["at"] != date:
            v["halt"] = True
        v.pop("at", None)
    d = {"date": date, "n": len(stocks), "analyzed": sorted(analyzed or []), "stocks": stocks}
    (out / "prices.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d
