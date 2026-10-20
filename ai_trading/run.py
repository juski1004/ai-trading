"""게임 실행기.

  python -m ai_trading.run start --days 30   새 게임 시작
  python -m ai_trading.run cycle             한 번 돌기 (장이 열린 시장만 매매)
  python -m ai_trading.run report            현재 성적표
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from .broker import Account, OrderRejected, VirtualBroker
from .config import GameRules
from .market import KST, YahooMarketData, is_market_open, market_of

GAME_DIR = Path("game")
STATE = GAME_DIR / "state.json"
JOURNAL = GAME_DIR / "journal.md"


def _log(text: str) -> None:
    GAME_DIR.mkdir(exist_ok=True)
    with JOURNAL.open("a") as f:
        f.write(text + "\n")
    print(text)


def _load(market) -> VirtualBroker:
    if not STATE.exists():
        raise SystemExit("진행 중인 게임이 없습니다. 먼저 'start' 를 실행하세요.")
    return VirtualBroker(Account.load(STATE), market)


def start(days: int) -> None:
    if STATE.exists():
        raise SystemExit(f"이미 게임이 있습니다 ({STATE}). 새로 하려면 그 파일을 지우세요.")
    b = VirtualBroker.new_game(days, YahooMarketData())
    b.acct.save(STATE)
    JOURNAL.unlink(missing_ok=True)
    _log(f"# 모의투자 게임\n\n- 기간: {b.acct.start_date} ~ {b.acct.end_date} ({days}일)\n"
         f"- 시작 자금: {b.acct.cash_krw:,.0f}원\n")


def cycle(now: datetime | None = None, market=None, llm=None) -> None:
    from .team import analyze

    now = now or datetime.now(tz=KST)
    market = market or YahooMarketData()
    b = _load(market)
    if b.is_finished(now.date()):
        print("게임 기간이 끝났습니다. 'report' 로 결과를 확인하세요.")
        return
    open_markets = [m for m in ("KR", "US") if is_market_open(m, now)]
    if not open_markets:
        print("지금은 열린 장이 없습니다.")
        return

    _log(f"\n## {now:%Y-%m-%d %H:%M} KST ({', '.join(open_markets)} 장중)")
    for m in open_markets:
        for t in b.check_stops(now, market=m):
            _log(f"- 🔔 {t.symbol} {t.qty}주 매도 · {t.reason} · 손익 {t.realized_krw:+,.0f}원")

    symbols = [s for s in dict.fromkeys([*b.rules.watchlist, *b.acct.positions])
               if market_of(s) in open_markets]
    cache: dict = {}
    verdicts = []
    for s in symbols:
        try:
            verdicts.append(analyze(s, b, cache, llm))
        except Exception as e:  # 데이터 오류 하나로 전체가 멈추지 않게
            _log(f"- ⚠️ {s} 분석 실패: {e}")

    # 매도 먼저 (현금 확보), 그다음 점수 높은 순으로 매수
    for v in sorted(verdicts, key=lambda v: (v.action != "SELL", -v.score)):
        try:
            if v.action == "SELL":
                t = b.sell(v.symbol, None, f"THEO 매도 판정 ({v.source})", now)
                _log(f"- 🔴 {v.symbol} {t.qty}주 매도 · 손익 {t.realized_krw:+,.0f}원 · {v.reason or v.score}")
            elif v.action == "BUY" and v.qty > 0:
                qty = min(v.qty, b.max_buy_qty(v.symbol))
                t = b.buy(v.symbol, qty, f"THEO 매수 판정 ({v.source})", now)
                _log(f"- 🟢 {v.symbol} {t.qty}주 매수 · {t.amount_krw:,.0f}원 · {v.reason or f'점수 {v.score:+.2f}'}")
        except OrderRejected as e:
            _log(f"- ⛔ {v.symbol} 주문 거절: {e}")

    holds = [f"{v.symbol}({v.score:+.2f})" for v in verdicts if v.action == "HOLD"]
    if holds:
        _log(f"- 관망: {', '.join(holds)}")
    eq = b.equity_krw()
    b.acct.equity_history.append([now.isoformat(timespec="minutes"), round(eq)])
    _log(f"- 총자산 {eq:,.0f}원 (현금 {b.acct.cash_krw:,.0f}원, 보유 {len(b.acct.positions)}종목)")
    b.acct.save(STATE)


def _benchmark(market, symbol: str, start: str) -> float | None:
    try:
        h = market.history(symbol, period="1y")["Close"]
        h = h[h.index.date >= date.fromisoformat(start)]
        return (h.iloc[-1] / h.iloc[0] - 1) * 100 if len(h) > 1 else None
    except Exception:
        return None


def report(market=None) -> str:
    market = market or YahooMarketData()
    b = _load(market)
    a, start_cash = b.acct, GameRules().starting_cash_krw
    eq = b.equity_krw()
    sells = [t for t in a.trades if t.side == "SELL"]
    wins = [t for t in sells if t.realized_krw > 0]
    peak, mdd = start_cash, 0.0
    for _, v in a.equity_history:
        peak = max(peak, v)
        mdd = min(mdd, (v / peak - 1) * 100)

    lines = [
        f"# 성적표 ({a.start_date} ~ {a.end_date}{', 종료' if b.is_finished() else ', 진행 중'})",
        f"- 총자산: {eq:,.0f}원 (수익률 {(eq / start_cash - 1) * 100:+.2f}%)",
        f"- 거래: 매수 {len(a.trades) - len(sells)}회, 매도 {len(sells)}회, "
        f"승률 {len(wins) / len(sells) * 100:.0f}%" if sells else "- 거래: 아직 매도 없음",
        f"- 최대 낙폭: {mdd:.2f}%",
    ]
    for name, sym in (("코스피", "^KS11"), ("S&P500", "^GSPC")):
        r = _benchmark(market, sym, a.start_date)
        if r is not None:
            lines.append(f"- 같은 기간 {name}: {r:+.2f}%")
    if a.positions:
        lines.append("- 보유 종목:")
        for s, p in a.positions.items():
            chg = (market.price(s) / p.avg_price - 1) * 100
            lines.append(f"  - {s} {p.qty}주 ({chg:+.1f}%)")
    text = "\n".join(lines)
    (GAME_DIR / "report.md").write_text(text + "\n")
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description="AI 모의투자 게임")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("start")
    sp.add_argument("--days", type=int, default=30, help="투자 기간 (7~90일)")
    sub.add_parser("cycle")
    sub.add_parser("report")
    args = ap.parse_args()

    if args.cmd == "start":
        start(args.days)
    elif args.cmd == "cycle":
        from .llm import from_env
        cycle(llm=from_env())
    else:
        print(report())


if __name__ == "__main__":
    main()
