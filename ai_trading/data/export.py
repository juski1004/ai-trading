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

import numpy as np
import pandas as pd

from . import collect
from .universe import fetch_listing_safe, universe

ECO_QUERY = "코스피 OR 환율 OR 기준금리 OR 소비자물가 OR 국제유가 OR 연준"


def _r(x, nd=2):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def day_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """시간대를 떼고 날짜만 남긴다. 야후가 시간대 붙은 날짜(Asia/Seoul)를 줄 때와 안 줄 때를 같은 모양으로 맞춘다."""
    idx = pd.DatetimeIndex(idx)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize().astype("datetime64[ns]")


def drop_unfinished_day(axis: pd.DatetimeIndex, now_kst: pd.Timestamp) -> pd.DatetimeIndex:
    """장중(15:40 KST 전)에 돌리면 오늘 막대는 아직 종가가 아니라서 뺀다."""
    if len(axis) and axis[-1].date() == now_kst.date() and (now_kst.hour, now_kst.minute) < (15, 40):
        return axis[:-1]
    return axis


def trading_axis(kospi_idx, stock_idxs: list, min_ratio: float = 0.5) -> pd.DatetimeIndex:
    """날짜축 = 코스피 지수 날짜 + 종목 절반 이상이 거래한 날짜.
    야후 코스피 지수에 하루가 빠지는 일이 있어서 (2026-10-22), 지수만 믿으면 그날 시세가 화면에서 통째로 사라진다."""
    axis = day_index(kospi_idx)
    if not stock_idxs:
        return axis
    counts = pd.Series(np.concatenate([day_index(i).unique().values for i in stock_idxs])).value_counts()
    busy = pd.DatetimeIndex(counts[counts >= len(stock_idxs) * min_ratio].index)
    busy = busy[busy >= axis.min()]
    return axis.union(busy).unique().sort_values()


MIN_STOCK_RATIO = 0.6  # 분석 대상 중 이 비율보다 적게 받으면 화면을 갱신하지 않는다


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

    def align(s: pd.Series) -> list:
        s = s.copy()
        s.index = day_index(s.index)
        s = s[~s.index.duplicated(keep="last")].reindex(axis).ffill().bfill()
        return [_r(v, 4) for v in s]

    px = collect.bars(syms + ["^KS11"])
    axis = trading_axis(kospi.index, [px[s].index for s in syms if px.get(s) is not None])
    axis = drop_unfinished_day(axis, pd.Timestamp.now(tz="Asia/Seoul"))
    dates = [d.date().isoformat() for d in axis]
    stocks = {}
    for s in syms:
        df = px.get(s)
        if df is None:
            print(f"- {s} 시세 없음, 건너뜀")
            continue
        df = df.copy()
        df.index = day_index(df.index)
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
        # 최근 10거래일은 거래소 정규장 값(네이버)으로 바로잡기 — 야후가 장중 값·잘못된 종가를 줄 때가 있음
        nd = collect.naver_daily(code)
        for k, d in enumerate(dates[-10:], start=len(dates) - 10):
            x = nd.get(d)
            if x:
                for f in ("o", "h", "l", "c"):
                    stocks[s][f][k] = round(x[f])
                stocks[s]["v"][k] = x["v"] or stocks[s]["v"][k]
        if not nd:
            print(f"- {s} 네이버 일봉 못 받음 (야후 값 그대로)")
        time.sleep(0.1)

    if len(stocks) < len(syms) * MIN_STOCK_RATIO:
        # 시세 서버가 빈 값을 준 날: 빈 화면을 올리지 않고 실패로 끝내서 어제 화면을 그대로 둔다
        raise SystemExit(f"시세를 {len(stocks)}/{len(syms)}종목만 받아 화면을 갱신하지 않습니다 (어제 화면 유지).")

    idx = px.get("^KS11")
    index_bars = None
    if idx is not None:
        idx = idx.copy()
        idx.index = day_index(idx.index)
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
        research = {}
        for s, st in stocks.items():
            nv = collect.naver_news(st["code"])
            seen = {x["title"] for x in nv}
            news["sym"][s] = nv + [x for x in collect.google_news(f'"{st["name"]}"', limit=15) if x["title"] not in seen]
            research[s] = collect.naver_research(st["code"])
            time.sleep(0.3)
        (out / "research.json").write_text(json.dumps(research, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for code, items in collect.dart_disclosures({st["code"] for st in stocks.values()}).items():
            s = next(k for k, st in stocks.items() if st["code"] == code)
            news["sym"].setdefault(s, []).extend(items)
        (out / "fin.json").write_text(json.dumps(fin, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (out / "news.json").write_text(json.dumps(news, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"재무·뉴스 저장 ({time.time() - t0:.0f}초)")


    try:
        cyc = collect.cycle_data()
        (out / "cycle.json").write_text(json.dumps(cyc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"시장 사이클 저장 (지수 {len(cyc['indices'])}개, 연준 {len(cyc['fed'])}회, 한은 {len(cyc['bok'])}회 변경)")
    except Exception as e:
        print(f"[시장 사이클 실패] {type(e).__name__}: {e}")

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

    # 많이 오르고 내린 종목: 기사 본문을 읽고 '왜 움직였나' 한 줄 + 호재·악재 (브리핑에 씀)
    if not quick:
        try:
            from ..llm import from_env as _why_llm
            from .why import build_why
            wy = build_why(stocks, news["sym"], dates, _why_llm())
            (out / "why.json").write_text(json.dumps(wy, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"오늘 움직인 이유 {len(wy['sym'])}종목 ({time.time() - t0:.0f}초)")
        except Exception as e:
            print(f"[움직인 이유 실패] {type(e).__name__}: {e}")
        try:  # 실적 발표 임박 종목 + 호재 전 진입 판단 (앱 알림)
            from .earnings import build_earnings
            ea = build_earnings(stocks, fin, dates[-1])
            (out / "earnings.json").write_text(json.dumps(ea, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        except Exception as e:
            print(f"[실적 발표 알림 실패] {type(e).__name__}: {e}")
        # 앱 '오늘의 리포트' 넘겨보기용 가벼운 묶음 (news.json 은 1MB 넘어 휴대폰에서 무거움)
        try:
            since = dates[-2] if len(dates) >= 2 else dates[-1]
            disc = [{"sym": s, "name": stocks[s]["name"], "date": x["date"], "title": x["title"], "link": x.get("link", "")}
                    for s, items in news["sym"].items() if s in stocks for x in items if x.get("src") == "DART" and x.get("date", "") >= since]
            disc.sort(key=lambda x: x["date"], reverse=True)
            eco = [{"date": x.get("date", ""), "title": x["title"], "src": x.get("src", ""), "link": x.get("link", "")} for x in news["eco"][:12]]
            (out / "deck.json").write_text(json.dumps({"date": dates[-1], "eco": eco, "disc": disc[:20]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        except Exception as e:
            print(f"[리포트 묶음 실패] {type(e).__name__}: {e}")

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
        from ..llm import from_env as _llm
        from .pick import build_pick
        pk = build_pick(out, _llm())
        (out / "pick.json").write_text(json.dumps(pk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"추천 종목: {pk.get('name') if pk.get('found') else '없음'}")
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
