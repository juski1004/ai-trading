"""무료 소스에서 데이터를 모은다. 하나가 실패해도 나머지는 계속 돌도록 각자 예외를 삼킨다."""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import pandas as pd
import requests

from .sentiment import headline_score

UA = {"User-Agent": "Mozilla/5.0 (ai-trading paper game)"}


WARNINGS: list[str] = []  # 이번 수집에서 실패한 항목 (자동 점검 알림에 씀)


def _warn(what: str, e: Exception) -> None:
    print(f"[{what} 실패] {type(e).__name__}: {str(e)[:120]}")
    WARNINGS.append(f"{what}: {type(e).__name__}")


# ---------------- 시세 ----------------
def bars(symbols: list[str], days: int = 430) -> dict[str, pd.DataFrame]:
    """일봉 OHLCV. 야후 파이낸스 무료 시세(15~20분 지연)."""
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    start = (date.today() - timedelta(days=days)).isoformat()
    for k in range(0, len(symbols), 40):  # 한 번에 너무 많이 요청하지 않게 나눠서
        chunk = symbols[k:k + 40]
        try:
            d = yf.download(chunk, start=start, progress=False, group_by="ticker", auto_adjust=False, threads=True)
        except Exception as e:
            _warn("시세", e)
            continue
        for s in chunk:
            try:
                df = (d[s] if len(chunk) > 1 else d)[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                if len(df) > 30:
                    out[s] = df
            except Exception:
                pass
    return out


# ---------------- 경제지표 ----------------
MACRO_TICKERS = {"usdkrw": "KRW=X", "dxy": "DX-Y.NYB", "wti": "CL=F", "gold": "GC=F",
                 "us10y": "^TNX", "vix": "^VIX", "kospi": "^KS11", "kosdaq": "^KQ11"}


def fred(series: str, days: int = 900) -> pd.Series | None:
    """FRED 시계열. FRED_API_KEY 가 있으면 API, 없으면 공개 CSV."""
    key = os.getenv("FRED_API_KEY")
    try:
        if key:
            r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                             params={"series_id": series, "api_key": key, "file_type": "json",
                                     "observation_start": (date.today() - timedelta(days=days)).isoformat()}, timeout=40)
            r.raise_for_status()
            obs = [(o["date"], o["value"]) for o in r.json()["observations"] if o["value"] not in (".", "")]
        else:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", timeout=90, headers=UA)
            r.raise_for_status()
            lines = r.text.strip().splitlines()[1:]
            obs = [tuple(x.split(",")[:2]) for x in lines if x.split(",")[1] not in (".", "")]
        s = pd.Series({pd.Timestamp(d): float(v) for d, v in obs}).sort_index()
        return s[s.index >= pd.Timestamp(date.today() - timedelta(days=days))]
    except Exception as e:
        _warn(f"FRED {series}", e)
        return None


def ecos(stat: str, cycle: str, item: str, start: str, end: str) -> pd.Series | None:
    """한국은행 ECOS. 키가 없으면 공개 sample 키(최근 10건까지만)."""
    key = os.getenv("ECOS_API_KEY") or "sample"
    n = 1000 if key != "sample" else 10
    try:
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/{n}/{stat}/{cycle}/{start}/{end}/{item}"
        rows = requests.get(url, timeout=30).json()["StatisticSearch"]["row"]
        return pd.Series({pd.Timestamp(r["TIME"][:4] + "-" + r["TIME"][4:6] + "-01"): float(r["DATA_VALUE"]) for r in rows}).sort_index()
    except Exception as e:
        _warn(f"ECOS {stat}", e)
        return None


def yoy(s: pd.Series | None) -> list[dict]:
    """월별 지수 → 전년 대비 상승률 발표 목록. 발표일은 다음 달 중순으로 근사."""
    if s is None or len(s) < 13:
        return []
    out = []
    for i in range(12, len(s)):
        m = s.index[i]
        rel = (m + pd.offsets.MonthBegin(1) + pd.Timedelta(days=12)).date().isoformat()
        out.append({"month": m.strftime("%Y-%m"), "value": round((s.iloc[i] / s.iloc[i - 12] - 1) * 100, 2), "date": rel})
    return out


def macro() -> dict:
    import yfinance as yf

    daily = {}
    start = (date.today() - timedelta(days=430)).isoformat()
    try:
        d = yf.download(list(MACRO_TICKERS.values()), start=start, progress=False, group_by="ticker", auto_adjust=False)
        for k, t in MACRO_TICKERS.items():
            try:
                daily[k] = d[t]["Close"].dropna()
            except Exception:
                pass
    except Exception as e:
        _warn("경제지표 시세", e)
    for k, tk in MACRO_TICKERS.items():  # 묶음 요청에서 빠진 지표는 하나씩 다시 받기
        if k in daily and len(daily[k]) > 30:
            continue
        try:
            s = yf.Ticker(tk).history(start=start, auto_adjust=False)["Close"].dropna()
            if len(s) > 30:
                daily[k] = s
            else:
                daily.pop(k, None)
        except Exception as e:
            _warn(f"경제지표 {tk}", e)
            daily.pop(k, None)

    us_cpi = yoy(fred("CPIAUCSL"))
    fed = fred("DFEDTARU")
    fed_changes = []
    if fed is not None:
        prev = None
        for d0, v in fed.items():
            if v != prev:
                fed_changes.append({"date": d0.date().isoformat(), "upper": v})
                prev = v
    today = date.today()
    kr = ecos("901Y009", "M", "0", f"{today.year - 2}01", today.strftime("%Y%m"))
    kr_cpi = yoy(kr) or yoy(fred("KORCPIALLMINMEI"))
    bok = ecos("722Y001", "M", "0101000", f"{today.year - 2}01", today.strftime("%Y%m"))
    bok_changes = []
    if bok is not None:
        prev = None
        for d0, v in bok.items():
            if v != prev:
                bok_changes.append({"date": d0.date().isoformat(), "rate": v})
                prev = v
    return {"daily": daily, "us_cpi": us_cpi, "kr_cpi": kr_cpi, "fed": fed_changes, "bok": bok_changes}



# ---------------- 큰 흐름: 10년 지수·금리 사이클 ----------------
CYCLE_INDICES = {"kospi": ("^KS11", "코스피"), "kosdaq": ("^KQ11", "코스닥"), "nasdaq": ("^IXIC", "나스닥"), "sp500": ("^GSPC", "S&P500")}


def cycle_data(years: int = 12) -> dict:
    """주봉 지수 12년, 연준·한국은행 기준금리 변경 기록, 미국 장단기 금리차(월)."""
    import yfinance as yf

    out: dict = {"indices": {}, "fed": [], "bok": [], "spread": []}
    for k, (tk, name) in CYCLE_INDICES.items():
        try:
            h = yf.Ticker(tk).history(period=f"{years}y", interval="1wk", auto_adjust=False)["Close"].dropna()
            out["indices"][k] = {"name": name, "d": [x.strftime("%Y-%m-%d") for x in h.index], "c": [round(float(v), 2) for v in h]}
        except Exception as e:
            _warn(f"장기 지수 {name}", e)
    days = years * 366
    for code in ("DFEDTARU", "DFEDTAR"):  # 2008-12 이후 상단, 그 이전은 단일 목표
        s = fred(code, days)
        if s is None:
            continue
        prev = None
        for d0, v in s.items():
            if v != prev:
                out["fed"].append({"date": d0.date().isoformat(), "rate": float(v)})
                prev = v
    out["fed"].sort(key=lambda x: x["date"])
    today = date.today()
    bok = ecos("722Y001", "M", "0101000", f"{today.year - years}01", today.strftime("%Y%m"))
    if bok is not None:
        prev = None
        for d0, v in bok.items():
            if v != prev:
                out["bok"].append({"date": d0.date().isoformat(), "rate": float(v)})
                prev = v
    sp = fred("T10Y2Y", days)
    if sp is not None:
        m = sp.resample("ME").last().dropna()
        out["spread"] = [[d0.strftime("%Y-%m"), round(float(v), 2)] for d0, v in m.items()]
    return out

# ---------------- 재무 ----------------
def financials(symbol: str) -> dict:
    """분기 매출·영업이익·순이익, 자본·부채, 상장주식수, 최근 1년 배당. (야후 파이낸스)"""
    import yfinance as yf

    t = yf.Ticker(symbol)
    out: dict = {"quarters": []}
    try:
        q = t.quarterly_income_stmt
        pick = lambda names: next((n for n in names if n in q.index), None)
        rev, op, ni = pick(["Total Revenue", "Operating Revenue"]), pick(["Operating Income", "Total Operating Income As Reported"]), pick(["Net Income", "Net Income Common Stockholders"])
        for col in sorted(q.columns):
            row = {"end": col.date().isoformat(),
                   # 실제 발표일은 분기 말 이후 약 한 달 (잠정실적 기준 근사)
                   "date": (col + pd.Timedelta(days=30)).date().isoformat()}
            for k, name in (("rev", rev), ("op", op), ("ni", ni)):
                v = q.at[name, col] if name else None
                row[k] = None if v is None or pd.isna(v) else float(v)
            if row["rev"] or row["op"]:
                out["quarters"].append(row)
    except Exception as e:
        _warn(f"{symbol} 손익", e)
    try:
        bs = t.quarterly_balance_sheet
        col = bs.columns[0]
        eq = bs.at["Stockholders Equity", col] if "Stockholders Equity" in bs.index else None
        li = next((bs.at[n, col] for n in ("Total Liabilities Net Minority Interest", "Total Liabilities") if n in bs.index), None)
        out["equity"] = None if eq is None or pd.isna(eq) else float(eq)
        out["liabilities"] = None if li is None or pd.isna(li) else float(li)
    except Exception as e:
        _warn(f"{symbol} 재무상태", e)
    try:
        out["shares"] = float(t.fast_info.get("shares") or 0) or None
    except Exception:
        out["shares"] = None
    try:
        dv = t.dividends
        dv = dv[dv.index >= pd.Timestamp(date.today() - timedelta(days=365), tz=dv.index.tz)]
        out["div_1y"] = float(dv.sum())
    except Exception:
        out["div_1y"] = None
    return out



def estimates(symbol: str) -> dict:
    """증권사 컨센서스: 분기·연간 예상 EPS·매출, 목표주가, 투자의견 분포. (야후 파이낸스, 커버 종목만)"""
    import yfinance as yf

    t, out = yf.Ticker(symbol), {}
    per = {"0q": "이번 분기", "+1q": "다음 분기", "0y": "올해", "+1y": "내년"}
    for key, attr in (("eps", "earnings_estimate"), ("rev", "revenue_estimate")):
        try:
            df = getattr(t, attr)
            rows = []
            for p, label in per.items():
                if df is not None and p in df.index:
                    r = df.loc[p]
                    g = lambda c: None if c not in r or pd.isna(r[c]) else float(r[c])
                    rows.append({"period": label, "avg": g("avg"), "low": g("low"), "high": g("high"),
                                 "n": g("numberOfAnalysts"), "year_ago": g("yearAgoEps" if key == "eps" else "yearAgoRevenue"), "growth": g("growth")})
            if rows:
                out[key] = rows
        except Exception:
            pass
    try:
        pt = t.analyst_price_targets or {}
        out["target"] = {k: float(pt[k]) for k in ("mean", "median", "high", "low") if pt.get(k)}
    except Exception:
        pass
    try:
        rs = t.recommendations_summary
        if rs is not None and len(rs):
            r = rs.iloc[0]
            out["rec"] = {k: int(r[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell") if k in r}
    except Exception:
        pass
    return out

# ---------------- 뉴스·공시 ----------------
def google_news(query: str, limit: int = 15) -> list[dict]:
    """구글 뉴스 RSS 헤드라인(제목·링크·언론사·날짜만, 본문은 가져오지 않음)."""
    url = f"https://news.google.com/rss/search?q={quote(query)}+when:60d&hl=ko&gl=KR&ceid=KR:ko"
    try:
        r = requests.get(url, timeout=20, headers=UA)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        _warn(f"뉴스 {query}", e)
        return []
    items = []
    for it in list(root.iter("item"))[:limit]:
        title = (it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if " - " in title and len(title.rsplit(" - ", 1)[1]) <= 20:  # 끝의 " - 언론사" 떼기
            title = title.rsplit(" - ", 1)[0]
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate")).astimezone().date().isoformat()
        except Exception:
            continue
        items.append({"date": dt, "title": title, "src": src, "link": it.findtext("link"), "score": headline_score(title)})
    return items


def dart_disclosures(stock_codes: set[str], days: int = 60) -> dict[str, list[dict]]:
    """DART 최근 공시 (DART_API_KEY 필요). {종목코드: [공시]}"""
    key = os.getenv("DART_API_KEY")
    if not key:
        return {}
    out: dict[str, list[dict]] = {}
    end, bgn = date.today(), date.today() - timedelta(days=days)
    for page in range(1, 31):
        try:
            r = requests.get("https://opendart.fss.or.kr/api/list.json", timeout=30,
                             params={"crtfc_key": key, "bgn_de": bgn.strftime("%Y%m%d"), "end_de": end.strftime("%Y%m%d"),
                                     "page_no": page, "page_count": 100, "last_reprt_at": "Y"}).json()
        except Exception as e:
            _warn("DART 공시", e)
            break
        if r.get("status") != "000":
            if r.get("status") != "013":  # 013 = 조회 결과 없음
                print(f"[DART] {r.get('status')} {r.get('message')}")
            break
        for x in r.get("list", []):
            code = x.get("stock_code") or ""
            if code in stock_codes:
                d = x["rcept_dt"]
                out.setdefault(code, []).append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "title": x["report_nm"].strip(), "src": "DART",
                                                 "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x['rcept_no']}",
                                                 "score": headline_score(x["report_nm"])})
        if page >= int(r.get("total_page", 1)):
            break
        time.sleep(0.2)
    return out


def now_kst() -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")
