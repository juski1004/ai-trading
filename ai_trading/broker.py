"""가상 증권 계좌: 주문 체결, 비용 계산, 안전장치, 자동 손절/익절."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import GameRules
from .market import KST, MarketData, currency_of, market_of


class OrderRejected(Exception):
    """안전장치나 잔고 부족으로 주문이 거절됨."""


@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float  # 현지 통화 기준 평균 매수가 (비용 제외)
    cost_krw: float   # 원화 기준 총 매수 비용 (수수료 포함)


@dataclass
class Trade:
    time: str
    symbol: str
    side: str        # "BUY" | "SELL"
    qty: int
    price: float     # 현지 통화 체결가 (미끄러짐 반영)
    fx: float        # 체결 시 환율 (국내는 1)
    fee_krw: float
    amount_krw: float  # 매수: 나간 돈, 매도: 들어온 돈
    reason: str
    realized_krw: float = 0.0  # 매도 시 실현 손익 (원화, 비용 포함)


@dataclass
class Account:
    start_date: str
    end_date: str
    cash_krw: float
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    day_start_equity: dict[str, float] = field(default_factory=dict)  # 날짜 -> 그날 시작 총자산
    equity_history: list[list] = field(default_factory=list)  # [시각, 총자산]

    # ---------- 저장 / 불러오기 ----------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> "Account":
        raw = json.loads(path.read_text())
        raw["positions"] = {k: Position(**v) for k, v in raw["positions"].items()}
        raw["trades"] = [Trade(**t) for t in raw["trades"]]
        return cls(**raw)


class VirtualBroker:
    def __init__(self, account: Account, market: MarketData, rules: GameRules = GameRules()):
        self.acct = account
        self.market = market
        self.rules = rules

    @classmethod
    def new_game(cls, days: int, market: MarketData, rules: GameRules = GameRules(),
                 start: date | None = None) -> "VirtualBroker":
        if not rules.min_days <= days <= rules.max_days:
            raise ValueError(f"투자 기간은 {rules.min_days}~{rules.max_days}일 사이여야 합니다.")
        start = start or datetime.now(tz=KST).date()
        acct = Account(start_date=start.isoformat(),
                       end_date=(start + timedelta(days=days)).isoformat(),
                       cash_krw=rules.starting_cash_krw)
        return cls(acct, market, rules)

    # ---------- 평가 ----------
    def _fx(self, symbol: str) -> float:
        return self.market.usdkrw() if currency_of(symbol) == "USD" else 1.0

    def position_value_krw(self, symbol: str) -> float:
        p = self.acct.positions[symbol]
        return p.qty * self.market.price(symbol) * self._fx(symbol)

    def equity_krw(self) -> float:
        return self.acct.cash_krw + sum(self.position_value_krw(s) for s in self.acct.positions)

    def is_finished(self, today: date | None = None) -> bool:
        today = today or datetime.now(tz=KST).date()
        return today >= date.fromisoformat(self.acct.end_date)

    # ---------- 비용 ----------
    def _fee_pct(self, symbol: str, side: str) -> float:
        r = self.rules
        if market_of(symbol) == "KR":
            return r.kr_commission_pct + (r.kr_sell_tax_pct if side == "SELL" else 0.0)
        return r.us_commission_pct

    # ---------- 안전장치 ----------
    def _mark_day(self, now: datetime) -> str:
        day = now.astimezone(KST).date().isoformat()
        self.acct.day_start_equity.setdefault(day, self.equity_krw())
        return day

    def daily_pnl_pct(self, now: datetime | None = None) -> float:
        now = now or datetime.now(tz=KST)
        start = self.acct.day_start_equity[self._mark_day(now)]
        return (self.equity_krw() / start - 1) * 100

    def max_buy_qty(self, symbol: str) -> int:
        """비중 한도와 현금 한도 안에서 살 수 있는 최대 수량."""
        price = self.market.price(symbol) * (1 + self.rules.slippage_pct / 100)
        unit_krw = price * self._fx(symbol) * (1 + self._fee_pct(symbol, "BUY") / 100)
        held = self.position_value_krw(symbol) if symbol in self.acct.positions else 0.0
        room = self.equity_krw() * self.rules.max_position_pct / 100 - held
        budget = min(room, self.acct.cash_krw)
        return max(0, math.floor(budget / unit_krw))

    # ---------- 주문 ----------
    def buy(self, symbol: str, qty: int, reason: str, now: datetime | None = None) -> Trade:
        now = now or datetime.now(tz=KST)
        self._mark_day(now)
        if self.is_finished(now.date()):
            raise OrderRejected("게임 기간이 끝났습니다.")
        if qty <= 0:
            raise OrderRejected("수량은 1주 이상이어야 합니다.")
        if self.daily_pnl_pct(now) <= self.rules.daily_loss_limit_pct:
            raise OrderRejected("오늘 손실 한도를 넘어 신규 매수가 중지되었습니다.")
        if symbol not in self.acct.positions and len(self.acct.positions) >= self.rules.max_positions:
            raise OrderRejected(f"동시 보유는 최대 {self.rules.max_positions}종목입니다.")
        if qty > self.max_buy_qty(symbol):
            raise OrderRejected("종목 비중 한도 또는 현금이 부족합니다.")

        fx = self._fx(symbol)
        price = self.market.price(symbol) * (1 + self.rules.slippage_pct / 100)
        gross = qty * price * fx
        fee = gross * self._fee_pct(symbol, "BUY") / 100
        self.acct.cash_krw -= gross + fee

        p = self.acct.positions.get(symbol)
        if p:
            p.avg_price = (p.avg_price * p.qty + price * qty) / (p.qty + qty)
            p.qty += qty
            p.cost_krw += gross + fee
        else:
            self.acct.positions[symbol] = Position(symbol, qty, price, gross + fee)

        return self._record(now, symbol, "BUY", qty, price, fx, fee, gross + fee, reason)

    def sell(self, symbol: str, qty: int | None, reason: str, now: datetime | None = None) -> Trade:
        """qty=None 이면 전량 매도. 손실 한도와 무관하게 매도는 항상 허용."""
        now = now or datetime.now(tz=KST)
        self._mark_day(now)
        p = self.acct.positions.get(symbol)
        if not p:
            raise OrderRejected(f"보유하지 않은 종목: {symbol}")
        qty = p.qty if qty is None else qty
        if not 0 < qty <= p.qty:
            raise OrderRejected("매도 수량이 보유 수량을 벗어났습니다.")

        fx = self._fx(symbol)
        price = self.market.price(symbol) * (1 - self.rules.slippage_pct / 100)
        gross = qty * price * fx
        fee = gross * self._fee_pct(symbol, "SELL") / 100
        self.acct.cash_krw += gross - fee

        sold_cost = p.cost_krw * qty / p.qty
        p.cost_krw -= sold_cost
        p.qty -= qty
        if p.qty == 0:
            del self.acct.positions[symbol]

        t = self._record(now, symbol, "SELL", qty, price, fx, fee, gross - fee, reason)
        t.realized_krw = round(gross - fee - sold_cost)
        return t

    def check_stops(self, now: datetime | None = None, market: str | None = None) -> list[Trade]:
        """손절/익절 기준에 닿은 종목을 자동 전량 매도. market 을 주면 그 시장만."""
        done = []
        for symbol, p in list(self.acct.positions.items()):
            if market and market_of(symbol) != market:
                continue
            change = (self.market.price(symbol) / p.avg_price - 1) * 100
            if change <= self.rules.stop_loss_pct:
                done.append(self.sell(symbol, None, f"자동 손절 ({change:.1f}%)", now))
            elif change >= self.rules.take_profit_pct:
                done.append(self.sell(symbol, None, f"자동 익절 (+{change:.1f}%)", now))
        return done

    def _record(self, now, symbol, side, qty, price, fx, fee, amount, reason) -> Trade:
        t = Trade(now.isoformat(timespec="seconds"), symbol, side, qty,
                  round(price, 4), round(fx, 4), round(fee), round(amount), reason)
        self.acct.trades.append(t)
        return t
