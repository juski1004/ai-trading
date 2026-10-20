from datetime import date, datetime

import pytest

from ai_trading.broker import Account, OrderRejected, VirtualBroker
from ai_trading.config import GameRules
from ai_trading.market import KST, is_market_open, market_of


class FakeMarket:
    def __init__(self, prices, fx=1300.0):
        self.prices, self.fx = dict(prices), fx

    def price(self, symbol):
        return self.prices[symbol]

    def usdkrw(self):
        return self.fx


NOW = datetime(2026, 10, 20, 10, 0, tzinfo=KST)
NO_COST = GameRules(kr_commission_pct=0, kr_sell_tax_pct=0, us_commission_pct=0, slippage_pct=0)


def new(prices, rules=NO_COST, fx=1300.0):
    return VirtualBroker.new_game(30, FakeMarket(prices, fx), rules, start=date(2026, 10, 20))


def test_period_limits():
    with pytest.raises(ValueError):
        VirtualBroker.new_game(3, FakeMarket({}))
    with pytest.raises(ValueError):
        VirtualBroker.new_game(91, FakeMarket({}))


def test_kr_buy_and_sell_with_costs():
    b = new({"005930.KS": 100_000}, rules=GameRules(slippage_pct=0))
    b.buy("005930.KS", 10, "test", NOW)
    assert b.acct.cash_krw == pytest.approx(10_000_000 - 1_000_000 * 1.00015)
    b.sell("005930.KS", None, "test", NOW)
    # 매도: 수수료 0.015% + 거래세 0.20%
    expected = 10_000_000 - 1_000_000 * 1.00015 + 1_000_000 * (1 - 0.00215)
    assert b.acct.cash_krw == pytest.approx(expected)
    assert b.acct.positions == {}


def test_us_stock_uses_fx():
    b = new({"AAPL": 100.0}, fx=1300)
    b.buy("AAPL", 10, "test", NOW)
    assert b.acct.cash_krw == pytest.approx(10_000_000 - 1_300_000)
    b.market.fx = 1400  # 환율 상승 → 원화 평가액 상승
    assert b.equity_krw() == pytest.approx(10_000_000 + 100_000)


def test_position_limit_20pct():
    b = new({"005930.KS": 100_000})
    assert b.max_buy_qty("005930.KS") == 20  # 1,000만 원의 20% = 200만 원
    with pytest.raises(OrderRejected):
        b.buy("005930.KS", 21, "test", NOW)


def test_max_five_positions():
    syms = [f"00000{i}.KS" for i in range(6)]
    b = new({s: 10_000 for s in syms})
    for s in syms[:5]:
        b.buy(s, 1, "test", NOW)
    with pytest.raises(OrderRejected):
        b.buy(syms[5], 1, "test", NOW)


def test_daily_loss_limit_blocks_buys_not_sells():
    b = new({"A.KS": 100_000, "B.KS": 100_000})
    b.buy("A.KS", 20, "test", NOW)  # 200만 원
    b.market.prices["A.KS"] = 80_000  # -40만 원 = 총자산 -4%
    with pytest.raises(OrderRejected):
        b.buy("B.KS", 1, "test", NOW)
    b.sell("A.KS", None, "test", NOW)  # 매도는 허용


def test_stop_loss_and_take_profit():
    b = new({"A.KS": 100_000, "B.KS": 100_000})
    b.buy("A.KS", 5, "test", NOW)
    b.buy("B.KS", 5, "test", NOW)
    b.market.prices.update({"A.KS": 94_000, "B.KS": 111_000})
    trades = b.check_stops(NOW)
    reasons = {t.symbol: t.reason for t in trades}
    assert "손절" in reasons["A.KS"] and "익절" in reasons["B.KS"]
    assert b.acct.positions == {}


def test_no_trading_after_end():
    b = new({"A.KS": 100_000})
    late = datetime(2026, 11, 19, 10, 0, tzinfo=KST)
    assert b.is_finished(late.date())
    with pytest.raises(OrderRejected):
        b.buy("A.KS", 1, "test", late)


def test_save_and_load(tmp_path):
    b = new({"AAPL": 100.0})
    b.buy("AAPL", 3, "test", NOW)
    path = tmp_path / "acct.json"
    b.acct.save(path)
    loaded = Account.load(path)
    assert loaded.positions["AAPL"].qty == 3
    assert loaded.trades[0].side == "BUY"


def test_market_hours():
    assert market_of("005930.KS") == "KR" and market_of("AAPL") == "US"
    assert is_market_open("KR", datetime(2026, 10, 20, 10, 0, tzinfo=KST))
    assert not is_market_open("KR", datetime(2026, 10, 20, 16, 0, tzinfo=KST))
    # 한국 시간 10/20 23:00 = 뉴욕 10/20 10:00 (장중)
    assert is_market_open("US", datetime(2026, 10, 20, 23, 0, tzinfo=KST))
    assert not is_market_open("US", datetime(2026, 10, 20, 10, 0, tzinfo=KST))
