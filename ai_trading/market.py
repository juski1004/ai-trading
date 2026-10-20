"""시세, 환율, 장 운영시간."""
from __future__ import annotations

from datetime import datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")


def market_of(symbol: str) -> str:
    """'005930.KS', '035720.KQ' -> 'KR', 그 외 -> 'US'."""
    return "KR" if symbol.upper().endswith((".KS", ".KQ")) else "US"


def currency_of(symbol: str) -> str:
    return "KRW" if market_of(symbol) == "KR" else "USD"


def is_market_open(market: str, now: datetime | None = None) -> bool:
    """정규장 여부 (공휴일은 아직 반영하지 않음)."""
    now = now or datetime.now(tz=KST)
    if market == "KR":
        local, start, end = now.astimezone(KST), time(9, 0), time(15, 30)
    else:
        local, start, end = now.astimezone(ET), time(9, 30), time(16, 0)
    return local.weekday() < 5 and start <= local.time() < end


def index_of(symbol: str) -> str:
    """종목이 속한 시장의 대표 지수: 코스피 또는 S&P500."""
    return "^KS11" if market_of(symbol) == "KR" else "^GSPC"


class MarketData(Protocol):
    def price(self, symbol: str) -> float: ...
    def usdkrw(self) -> float: ...


class YahooMarketData:
    """야후 파이낸스 무료 시세 (15~20분 지연)."""

    def __init__(self) -> None:
        import yfinance as yf  # 테스트에서는 불러오지 않도록 여기서 import
        self._yf = yf

    def _last_close(self, ticker: str) -> float:
        hist = self._yf.Ticker(ticker).history(period="5d", interval="1d")
        if hist.empty:
            raise ValueError(f"시세를 찾을 수 없음: {ticker}")
        return float(hist["Close"].iloc[-1])

    def price(self, symbol: str) -> float:
        return self._last_close(symbol)

    def usdkrw(self) -> float:
        return self._last_close("KRW=X")

    def history(self, symbol: str, period: str = "6mo"):
        """일봉 (Open, High, Low, Close, Volume)."""
        hist = self._yf.Ticker(symbol).history(period=period, interval="1d")
        if hist.empty:
            raise ValueError(f"차트 데이터를 찾을 수 없음: {symbol}")
        return hist
