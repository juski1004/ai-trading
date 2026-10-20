"""종목 목록과 AI 분석 대상(유니버스).

- 전체 목록: KRX 상장법인목록(KIND)에서 코스피·코스닥 전 종목을 받는다. 화면의 종목 검색용.
- 분석 대상: 전 종목을 매일 분석하면 무료 시세 한도에 걸리므로 대형주 위주로 제한한다.
  `AI_UNIVERSE` 환경변수(쉼표로 구분한 6자리 코드)로 바꿀 수 있다.
"""
from __future__ import annotations

import io
import os

import pandas as pd
import requests

KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={m}"
MARKETS = {"stockMkt": ("KOSPI", ".KS"), "kosdaqMkt": ("KOSDAQ", ".KQ")}

# 시가총액·거래대금 상위권 위주 기본 분석 대상 (코드, 시장 접미사)
DEFAULT_UNIVERSE: tuple[str, ...] = (
    # 코스피
    "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "000270.KS", "068270.KS",
    "035420.KS", "105560.KS", "055550.KS", "005490.KS", "028260.KS", "012330.KS", "051910.KS",
    "006400.KS", "035720.KS", "086790.KS", "032830.KS", "000810.KS", "096770.KS", "034730.KS",
    "066570.KS", "015760.KS", "033780.KS", "329180.KS", "012450.KS", "034020.KS", "009150.KS",
    "010140.KS", "042660.KS", "010130.KS", "003670.KS", "009540.KS", "003550.KS", "017670.KS",
    "030200.KS", "316140.KS", "138040.KS", "323410.KS", "259960.KS", "036570.KS", "086280.KS",
    "042700.KS", "079550.KS", "064350.KS", "047810.KS", "010950.KS", "003490.KS", "011200.KS",
    "090430.KS", "352820.KS", "018260.KS", "011070.KS", "000720.KS", "000100.KS", "128940.KS",
    "326030.KS", "271560.KS", "097950.KS", "011170.KS", "009830.KS",
    # 코스닥
    "247540.KQ", "086520.KQ", "196170.KQ", "028300.KQ", "141080.KQ", "000250.KQ", "277810.KQ",
    "263750.KQ", "214150.KQ", "214450.KQ", "145020.KQ", "058470.KQ", "039030.KQ", "357780.KQ",
    "240810.KQ", "035900.KQ", "041510.KQ",
)


def universe() -> list[str]:
    env = os.getenv("AI_UNIVERSE")
    if not env:
        return list(DEFAULT_UNIVERSE)
    listing = {c: s for c, _, _, s in fetch_listing_safe()}
    out = []
    for code in (x.strip() for x in env.split(",") if x.strip()):
        out.append(code if "." in code else code + listing.get(code, ".KS"))
    return out


def fetch_listing() -> list[tuple[str, str, str, str]]:
    """[(6자리 코드, 회사명, 시장, 야후 접미사)] 코스피·코스닥 전 종목."""
    rows = []
    for mkt, (label, suffix) in MARKETS.items():
        r = requests.get(KIND_URL.format(m=mkt), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        df = pd.read_html(io.StringIO(r.content.decode("euc-kr", errors="replace")), converters={"종목코드": str})[0]
        for _, x in df.iterrows():
            code = str(x["종목코드"]).strip().zfill(6)  # 새 종목코드는 영문이 섞임 (예: 0220W0)
            rows.append((code, str(x["회사명"]), label, suffix, str(x.get("업종", ""))))
    return [(c, n, m, s) for c, n, m, s, _ in rows]


def fetch_listing_safe() -> list[tuple[str, str, str, str]]:
    try:
        return fetch_listing()
    except Exception as e:  # KIND 접속 실패 시 분석 대상만이라도 쓰도록
        print(f"[종목 목록 받기 실패] {type(e).__name__}: {str(e)[:100]}")
        return [(s.split(".")[0], s, "KOSPI" if s.endswith(".KS") else "KOSDAQ", s[-3:]) for s in DEFAULT_UNIVERSE]
