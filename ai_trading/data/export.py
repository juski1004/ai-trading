"""웹 화면용 데이터(JSON) 만들기.

  python -m ai_trading.data.export --out web/data          전체 (분석 대상 종목 시세·재무·뉴스, 경제지표)
  python -m ai_trading.data.export --out web/data --quick  재무·뉴스 생략 (빠른 확인용)

결과 파일
  meta.json      갱신 시각, 사용한 키
  listing.json   코스피·코스닥 전 종목 [코드, 이름, 시장]
  market.json    날짜축, 분석 대상 종목 일봉, 지수·환율·유가 등 일별 경제지표, 물가·금리 발표
  fin.json       분석 대상 종목 분기 실적·자본·부채·주식수·배당
  news.json      경제·종목 뉴스와 공시 헤드라인
  summary.json   종목별 최근 뉴스 AI 3줄 요약 (GEMINI_API_KEY 있을 때)
  scores.json    앱 홈·분석용 종목별 AI 점수 (참고용)
  ai.json        엔진(실전 AI 계좌) 상태와 최근 판정
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd

from . import collect
from .universe import fetch_listing_safe, universe

ECO_QUERY = "코스피 OR 환율 OR 기준금리 OR 소비자물가 OR 국제유가 OR 연준"


def _r(x, nd=2):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def build(out: Path, quick: bool = False, game_dir: Path = Path("game")) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    listing = fetch_listing_safe()
    names = {c: n for c, n, _, _ in listing}
    syms = universe()
    print(f"종목 목록 {len(listing)}개, 분석 대상 {len(syms)}개")

    mac = collect.macro()
    kospi = mac["daily"].get("kospi")
    if kospi is None or len(kospi) < 150:
        raise SystemExit("코스피 지수를 받지 못해 날짜축을 만들 수 없습니다.")
    axis = kospi.index.normalize()
    dates = [d.date().isoformat() for d in axis]

    def align(s: pd.Series) -> list:
        s = s.copy()
        s.index = s.index.tz_localize(None).normalize() if s.index.tz is not None else s.index.normalize()
        s = s[~s.index.duplicated(keep="last")].reindex(axis).ffill().bfill()
        return [_r(v, 4) for v in s]

    px = collect.bars(syms + ["^KS11"])
    stocks = {}
    for s in syms:
        df = px.get(s)
        if df is None:
            print(f"- {s} 시세 없음, 건너뜀")
            continue
        df = df.copy()
        df.index = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index.normalize()
        df = df[~df.index.duplicated(keep="last")].reindex(axis)
        df["Close"] = df["Close"].ffill()
        for k in ("Open", "High", "Low"):
            df[k] = df[k].fillna(df["Close"])
        df["Volume"] = df["Volume"].fillna(0)
        df = df.dropna(subset=["Close"])
        if len(df) < len(axis) * 0.7:  # 상장한 지 얼마 안 된 종목 등
            print(f"- {s} 데이터 부족({len(df)}일), 건너뜀")
            continue
        df = df.reindex(axis).bfill()
        code = s.split(".")[0]
        stocks[s] = {"sym": s, "code": code, "name": names.get(code, code), "market": "KOSPI" if s.endswith(".KS") else "KOSDAQ",
                     "o": [round(v) for v in df["Open"]], "h": [round(v) for v in df["High"]], "l": [round(v) for v in df["Low"]],
                     "c": [round(v) for v in df["Close"]], "v": [int(v) for v in df["Volume"]]}

    idx = px.get("^KS11")
    index_bars = None
    if idx is not None:
        idx = idx.copy()
        idx.index = idx.index.tz_localize(None).normalize() if idx.index.tz is not None else idx.index.normalize()
        idx = idx[~idx.index.duplicated(keep="last")].reindex(axis).ffill().bfill()
        index_bars = {k: [_r(v) for v in idx[c]] for k, c in (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"))}

    market = {"dates": dates, "stocks": stocks, "index": index_bars,
              "macro": {k: align(v) for k, v in mac["daily"].items()},
              "releases": {"us_cpi": mac["us_cpi"], "kr_cpi": mac["kr_cpi"], "fed": mac["fed"], "bok": mac["bok"]}}
    (out / "market.json").write_text(json.dumps(market, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / "listing.json").write_text(json.dumps([[c, n, m] for c, n, m, _ in listing], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"시세·경제지표 저장 ({len(stocks)}종목, {time.time() - t0:.0f}초)")

    fin, news = {}, {"eco": [], "sym": {}}
    if not quick:
        for k, s in enumerate(stocks):
            fin[s] = collect.financials(s)
            try:
                fin[s]["est"] = collect.estimates(s)
            except Exception as e:
                print(f"[{s} 컨센서스 실패] {type(e).__name__}")
            if k % 10 == 9:
                print(f"  재무 {k + 1}/{len(stocks)}")
        news["eco"] = collect.google_news(ECO_QUERY, limit=40)
        for s, st in stocks.items():
            news["sym"][s] = collect.google_news(f'"{st["name"]}"', limit=15)
            time.sleep(0.3)
        for code, items in collect.dart_disclosures({st["code"] for st in stocks.values()}).items():
            s = next(k for k, st in stocks.items() if st["code"] == code)
            news["sym"].setdefault(s, []).extend(items)
        (out / "fin.json").write_text(json.dumps(fin, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (out / "news.json").write_text(json.dumps(news, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"재무·뉴스 저장 ({time.time() - t0:.0f}초)")


    # 수급 (외국인·기관·개인) + 수급 전망, 오늘의 시장 전망
    from . import flows as fl
    from .outlook import write as write_outlook
    try:
        sflows = fl.all_stock_flows([st["code"] for st in stocks.values()])
        mflows = fl.market_flows()
        fo = {}
        for s, st in stocks.items():
            rows = sflows.get(st["code"])
            if rows:
                cl = {d: c for d, c in zip(dates, st["c"])}
                fo[s] = fl.flow_outlook(rows, [cl.get(r["date"], st["c"][-1]) for r in rows])
        # 대형주 합계 (금액, 원): 날짜별 외국인·기관·개인
        agg: dict[str, dict] = {}
        for s, st in stocks.items():
            cl = {d: c for d, c in zip(dates, st["c"])}
            for r in sflows.get(st["code"], []):
                a = agg.setdefault(r["date"], {"frg": 0.0, "org": 0.0, "ind": 0.0})
                for k2 in ("frg", "org", "ind"):
                    a[k2] += r[k2] * cl.get(r["date"], st["c"][-1])
        big = [{"date": d, **{k2: round(v) for k2, v in a.items()}} for d, a in sorted(agg.items())]
        big5 = {k2: round(sum(x[k2] for x in big[-5:]) / 1e8) for k2 in ("frg", "org", "ind")} if big else None
        (out / "flows.json").write_text(json.dumps({"market": mflows, "big": big, "stocks": {s: sflows.get(st["code"], []) for s, st in stocks.items()},
                                                    "outlook": fo}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        above = sum(1 for st in stocks.values() if st["c"][-1] > sum(st["c"][-20:]) / 20)
        ol = write_outlook(mac["daily"], mflows, big5, news["eco"], {"전체": len(stocks), "20일선_위": above})
        (out / "outlook.json").write_text(json.dumps({"date": dates[-1], **ol}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"수급 {len(sflows)}종목·시장 전망({ol.get('source')}) 저장 ({time.time() - t0:.0f}초)")
    except Exception as e:
        print(f"[수급·시장 전망 실패] {type(e).__name__}: {e}")

    # AI 뉴스 요약은 무료 한도를 많이 쓰므로 시장 전망 다음에
    if not quick:
            from ..llm import from_env
            from .summary import summarize
            summ = summarize(news["sym"], {s: st["name"] for s, st in stocks.items()}, from_env())
            (out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"AI 뉴스 요약 {len(summ)}종목 ({time.time() - t0:.0f}초)")

    from .scores import build_scores
    try:
        sc = build_scores(market, news["sym"] or None, fin or None)
        (out / "scores.json").write_text(json.dumps(sc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"AI 점수 {len(sc['stocks'])}종목")
    except Exception as e:  # 점수 실패로 화면 데이터 전체를 버리지 않게
        print(f"[AI 점수 실패] {type(e).__name__}: {e}")

    ai = {}
    for name in ("state.json", "verdicts.json"):
        p = game_dir / name
        if p.exists():
            ai[name.split(".")[0]] = json.loads(p.read_text(encoding="utf-8"))
    (out / "ai.json").write_text(json.dumps(ai, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    meta = {"updated": collect.now_kst(), "stocks": len(stocks), "listing": len(listing),
            "keys": {k: bool(os.getenv(k)) for k in ("FRED_API_KEY", "ECOS_API_KEY", "DART_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "XAI_API_KEY")},
            "warnings": collect.WARNINGS[:50]}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"완료 {time.time() - t0:.0f}초")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description="웹 화면용 데이터 만들기")
    ap.add_argument("--out", default="web/data")
    ap.add_argument("--quick", action="store_true", help="재무·뉴스 생략")
    a = ap.parse_args()
    build(Path(a.out), quick=a.quick)


if __name__ == "__main__":
    main()
