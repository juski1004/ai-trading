"""한 종목에 대해 AI 6명이 차례로 의견을 내고 THEO가 판정한다."""
from __future__ import annotations

from .agents import Verdict, joy, lloyd, miles, oscar, ray, theo
from .broker import VirtualBroker
from .market import index_of

INDEX_NAMES = {"^KS11": "코스피", "^GSPC": "S&P500"}


def analyze(symbol: str, broker: VirtualBroker, index_cache: dict | None = None) -> Verdict:
    market, rules = broker.market, broker.rules
    index_cache = index_cache if index_cache is not None else {}
    idx = index_of(symbol)
    if idx not in index_cache:
        index_cache[idx] = market.history(idx)

    df = market.history(symbol)
    held = symbol in broker.acct.positions
    max_qty = broker.max_buy_qty(symbol)

    opinions = [joy(index_cache[idx], INDEX_NAMES[idx]), oscar(df), ray(df)]
    m_op, plan = miles(df, rules, max_qty)
    opinions.append(m_op)
    risk = lloyd(df, rules, held=held, n_positions=len(broker.acct.positions),
                 daily_pnl_pct=broker.daily_pnl_pct(), max_qty=max_qty)
    return theo(symbol, opinions, risk, rules, held=held, max_qty=max_qty, plan=plan)


if __name__ == "__main__":
    import sys

    from .market import YahooMarketData

    b = VirtualBroker.new_game(30, YahooMarketData())
    cache: dict = {}
    for s in sys.argv[1:] or b.rules.watchlist:
        print(analyze(s, b, cache).explain(), "\n")
