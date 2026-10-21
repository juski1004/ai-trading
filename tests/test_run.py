from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from ai_trading import run
from ai_trading.broker import Account, VirtualBroker
from ai_trading.config import GameRules
from ai_trading.market import KST


def chart(closes):
    c = pd.Series(closes, dtype=float, index=pd.date_range("2026-07-01", periods=len(closes)))
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1000.0})


class FakeMarket:
    def __init__(self):
        up = chart(np.linspace(100, 104, 80))  # 완만한 상승 → 20일선 근처
        self.charts = {s: up for s in GameRules().watchlist}
        self.charts.update({"^KS11": up, "^GSPC": up})

    def price(self, s):
        return float(self.charts[s]["Close"].iloc[-1])

    def usdkrw(self):
        return 1300.0

    def history(self, s, period="6mo"):
        return self.charts[s]


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "GAME_DIR", tmp_path)
    monkeypatch.setattr(run, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(run, "JOURNAL", tmp_path / "journal.md")
    m = FakeMarket()
    VirtualBroker.new_game(30, m, start=date(2026, 10, 20)).acct.save(tmp_path / "state.json")
    return tmp_path, m


def test_cycle_buys_only_open_market(game):
    path, m = game
    run.cycle(datetime(2026, 10, 20, 10, 0, tzinfo=KST), market=m, with_context=False)  # 한국 장중
    acct = Account.load(path / "state.json")
    assert acct.positions and all(s.endswith((".KS", ".KQ")) for s in acct.positions)
    assert (path / "verdicts.json").exists()
    assert len(acct.positions) <= 5
    assert "총자산" in (path / "journal.md").read_text(encoding="utf-8")


def test_cycle_does_nothing_when_closed(game):
    path, m = game
    run.cycle(datetime(2026, 10, 25, 12, 0, tzinfo=KST), market=m, with_context=False)  # 일요일
    assert Account.load(path / "state.json").trades == []


def test_report(game):
    path, m = game
    run.cycle(datetime(2026, 10, 20, 10, 0, tzinfo=KST), market=m, with_context=False)
    text = run.report(market=m)
    assert "수익률" in text and (path / "report.md").exists()


def test_cycle_trades_once_per_day(game):
    path, m = game
    run.cycle(datetime(2026, 10, 20, 10, 0, tzinfo=KST), market=m, with_context=False)
    n = len(Account.load(path / "state.json").trades)
    run.cycle(datetime(2026, 10, 20, 14, 0, tzinfo=KST), market=m, with_context=False)
    acct = Account.load(path / "state.json")
    assert len(acct.trades) == n and len(acct.equity_history) == 1
