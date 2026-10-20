"""AI 6명. 지금은 무료 규칙 기반 분석이고, 나중에 AI 모델로 바꿀 수 있다.

점수는 -1(강한 매도) ~ +1(강한 매수).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .config import GameRules


@dataclass
class Opinion:
    agent: str
    score: float
    summary: str


@dataclass
class RiskCheck:
    approved: bool
    reasons: list[str]


@dataclass
class Verdict:
    symbol: str
    action: str  # "BUY" | "SELL" | "HOLD"
    score: float
    qty: int
    opinions: list[Opinion]
    risk: RiskCheck
    plan: dict = field(default_factory=dict)

    def explain(self) -> str:
        lines = [f"[{self.symbol}] THEO 판정: {self.action} (점수 {self.score:+.2f}, 수량 {self.qty})"]
        lines += [f"  {o.agent:<5} {o.score:+.2f}  {o.summary}" for o in self.opinions]
        lines.append(f"  LLOYD {'통과' if self.risk.approved else '거절'}  {'; '.join(self.risk.reasons)}")
        return "\n".join(lines)


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def rsi(close: pd.Series, n: int = 14) -> float:
    diff = close.diff()
    gain = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    return float(100 - 100 / (1 + gain.iloc[-1] / last_loss))


def atr_pct(df: pd.DataFrame, n: int = 14) -> float:
    prev = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-1] / df["Close"].iloc[-1] * 100)


# ---------------- JOY: 시장 리포트 ----------------
def joy(index_df: pd.DataFrame, index_name: str) -> Opinion:
    c = index_df["Close"]
    last, ma20, ma60 = c.iloc[-1], c.rolling(20).mean().iloc[-1], c.rolling(60).mean().iloc[-1]
    chg5 = (last / c.iloc[-6] - 1) * 100
    score = 0.4 * (1 if last > ma20 else -1) + 0.3 * (1 if ma20 > ma60 else -1) + 0.3 * _clamp(chg5 / 3)
    mood = "상승 흐름" if score > 0.2 else "하락 흐름" if score < -0.2 else "방향 없음"
    return Opinion("JOY", _clamp(score), f"{index_name} {mood}, 5일 {chg5:+.1f}%")


# ---------------- OSCAR: 거래소 데이터 ----------------
def oscar(df: pd.DataFrame) -> Opinion:
    c, v = df["Close"], df["Volume"]
    avg_vol = v.iloc[-21:-1].mean()
    vol_ratio = float(v.iloc[-1] / avg_vol) if avg_vol else 1.0
    chg1 = (c.iloc[-1] / c.iloc[-2] - 1) * 100
    chg5 = (c.iloc[-1] / c.iloc[-6] - 1) * 100
    if vol_ratio >= 1.5:
        score = 0.8 if chg1 > 0 else -0.8
        note = "거래량 급증 + " + ("상승" if chg1 > 0 else "하락")
    else:
        score = _clamp(chg5 / 6)
        note = "평범한 거래량"
    return Opinion("OSCAR", score, f"{note} (평소 대비 {vol_ratio:.1f}배), 하루 {chg1:+.1f}%")


# ---------------- RAY: 차트 분석 ----------------
def ray(df: pd.DataFrame) -> Opinion:
    c = df["Close"]
    ma5, ma20 = c.rolling(5).mean().iloc[-1], c.rolling(20).mean().iloc[-1]
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = float((macd - macd.ewm(span=9, adjust=False).mean()).iloc[-1])
    r = rsi(c)
    score = 0.4 * (1 if ma5 > ma20 else -1) + 0.3 * (1 if hist > 0 else -1)
    if r < 30:
        score += 0.3
    elif r > 70:
        score -= 0.3
    trend = "단기 상승추세" if ma5 > ma20 else "단기 하락추세"
    return Opinion("RAY", _clamp(score), f"{trend}, MACD {'양' if hist > 0 else '음'}, RSI {r:.0f}")


# ---------------- MILES: 진입 계획 ----------------
def miles(df: pd.DataFrame, rules: GameRules, max_qty: int) -> tuple[Opinion, dict]:
    c = df["Close"]
    last, ma20 = float(c.iloc[-1]), float(c.rolling(20).mean().iloc[-1])
    gap = (last / ma20 - 1) * 100
    if gap < 0:
        score, note = -0.3, "20일선 아래, 진입 보류"
    elif gap <= 5:
        score, note = 0.5, "20일선 근처, 진입 적기"
    elif gap <= 10:
        score, note = 0.1, "다소 올라온 자리"
    else:
        score, note = -0.5, "많이 오른 자리, 추격 매수 위험"
    plan = {
        "entry": round(last, 2),
        "stop": round(last * (1 + rules.stop_loss_pct / 100), 2),
        "target": round(last * (1 + rules.take_profit_pct / 100), 2),
        "qty": max_qty,
    }
    return Opinion("MILES", score, f"{note} (20일선 대비 {gap:+.1f}%), 최대 {max_qty}주"), plan


# ---------------- LLOYD: 리스크 점검 ----------------
def lloyd(df: pd.DataFrame, rules: GameRules, *, held: bool, n_positions: int,
          daily_pnl_pct: float, max_qty: int) -> RiskCheck:
    reasons, ok = [], True
    vol = atr_pct(df)
    if vol > rules.max_volatility_pct:
        ok = False
        reasons.append(f"변동성 과다 (하루 평균 {vol:.1f}%)")
    if daily_pnl_pct <= rules.daily_loss_limit_pct:
        ok = False
        reasons.append(f"오늘 손실 한도 도달 ({daily_pnl_pct:.1f}%)")
    if not held and n_positions >= rules.max_positions:
        ok = False
        reasons.append(f"보유 종목 {rules.max_positions}개 꽉 참")
    if max_qty <= 0:
        ok = False
        reasons.append("살 수 있는 수량 없음 (비중 한도·현금)")
    if ok:
        reasons.append(f"변동성 {vol:.1f}%, 이상 없음")
    return RiskCheck(ok, reasons)


# ---------------- THEO: 최종 판정 ----------------
WEIGHTS = {"JOY": 0.20, "OSCAR": 0.20, "RAY": 0.35, "MILES": 0.25}


def theo(symbol: str, opinions: list[Opinion], risk: RiskCheck, rules: GameRules,
         *, held: bool, max_qty: int, plan: dict) -> Verdict:
    score = sum(WEIGHTS[o.agent] * o.score for o in opinions)
    if held and score <= rules.sell_threshold:
        action, qty = "SELL", 0  # 0 = 전량
    elif score >= rules.buy_threshold and risk.approved:
        action, qty = "BUY", max_qty
    else:
        action, qty = "HOLD", 0
    return Verdict(symbol, action, round(score, 3), qty, opinions, risk, plan)
