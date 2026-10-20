"""한 종목에 대해 AI 6명이 차례로 의견을 내고 THEO가 판정한다."""
from __future__ import annotations

from .agents import Verdict, joy, lloyd, miles, oscar, ray, theo, theo_ai
from .broker import VirtualBroker
from .market import index_of

INDEX_NAMES = {"^KS11": "코스피", "^GSPC": "S&P500"}


def analyze(symbol: str, broker: VirtualBroker, index_cache: dict | None = None, llm=None, ctx: dict | None = None) -> Verdict:
    """ctx: {'macro': Macro, 'news': {심볼: (점수, 제목)}} (없으면 시세 규칙만 사용)"""
    ctx = ctx or {}
    market, rules = broker.market, broker.rules
    index_cache = index_cache if index_cache is not None else {}
    idx = index_of(symbol)
    if idx not in index_cache:
        index_cache[idx] = market.history(idx)

    df = market.history(symbol)
    held = symbol in broker.acct.positions
    max_qty = broker.max_buy_qty(symbol)

    macro = ctx.get("macro") if idx == "^KS11" else None
    opinions = [joy(index_cache[idx], INDEX_NAMES[idx], macro), oscar(df, ctx.get("news", {}).get(symbol)), ray(df)]
    m_op, plan = miles(df, rules, max_qty)
    opinions.append(m_op)
    risk = lloyd(df, rules, held=held, n_positions=len(broker.acct.positions),
                 daily_pnl_pct=broker.daily_pnl_pct(), max_qty=max_qty)
    verdict = theo(symbol, opinions, risk, rules, held=held, max_qty=max_qty, plan=plan)
    if llm is not None:
        verdict = theo_ai(llm, verdict, held=held, max_qty=max_qty)
    return verdict


if __name__ == "__main__":
    import sys

    from .llm import from_env
    from .market import YahooMarketData

    llm = from_env()
    print("THEO 모드:", "무료 AI (Gemini)" if llm else "규칙 기반 (GEMINI_API_KEY 없음)", "\n")
    b = VirtualBroker.new_game(30, YahooMarketData())
    cache: dict = {}
    for s in sys.argv[1:] or b.rules.watchlist:
        print(analyze(s, b, cache, llm).explain(), "\n")
