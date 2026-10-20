import numpy as np
import pandas as pd

from ai_trading.agents import RiskCheck, joy, lloyd, miles, oscar, ray, rsi, theo
from ai_trading.config import GameRules

R = GameRules()


def chart(closes, vol=None):
    c = pd.Series(closes, dtype=float)
    v = pd.Series(vol if vol is not None else [1000] * len(c), dtype=float)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": v})


UP = chart(np.linspace(100, 130, 80))
DOWN = chart(np.linspace(130, 100, 80))


def test_rsi_extremes():
    assert rsi(UP["Close"]) > 70
    assert rsi(DOWN["Close"]) < 30


def test_joy_and_ray_follow_trend():
    assert joy(UP, "X").score > 0 > joy(DOWN, "X").score
    assert ray(UP).score > ray(DOWN).score


def test_oscar_volume_spike():
    closes = [100] * 30 + [105]
    vols = [1000] * 30 + [3000]
    assert oscar(chart(closes, vols)).score == 0.8


def test_miles_plan_uses_rules():
    _, plan = miles(UP, R, 7)
    assert plan["stop"] < plan["entry"] < plan["target"] and plan["qty"] == 7


def test_lloyd_rejects_when_full_or_volatile():
    calm = lloyd(UP, R, held=False, n_positions=0, daily_pnl_pct=0, max_qty=5)
    assert calm.approved
    full = lloyd(UP, R, held=False, n_positions=5, daily_pnl_pct=0, max_qty=5)
    assert not full.approved
    wild = chart([100, 110] * 40)
    assert not lloyd(wild, R, held=False, n_positions=0, daily_pnl_pct=0, max_qty=5).approved


def test_theo_needs_lloyd_approval():
    ops = [joy(UP, "X"), oscar(UP), ray(UP), miles(UP, R, 3)[0]]
    ok = theo("A", ops, RiskCheck(True, []), R, held=False, max_qty=3, plan={})
    no = theo("A", ops, RiskCheck(False, ["x"]), R, held=False, max_qty=3, plan={})
    assert ok.action == "BUY" and ok.qty == 3
    assert no.action == "HOLD"


def test_theo_sells_held_on_bad_score():
    ops = [joy(DOWN, "X"), oscar(DOWN), ray(DOWN), miles(DOWN, R, 0)[0]]
    v = theo("A", ops, RiskCheck(False, []), R, held=True, max_qty=0, plan={})
    assert v.action == "SELL"


from ai_trading.agents import theo_ai


class FakeLLM:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def ask_json(self, prompt):
        self.prompts.append(prompt)
        return self.answer


def _rule(risk_ok=True):
    ops = [joy(UP, "X"), oscar(UP), ray(UP), miles(UP, R, 3)[0]]
    return theo("A", ops, RiskCheck(risk_ok, ["x"]), R, held=False, max_qty=3, plan={})


def test_ai_verdict_used():
    v = theo_ai(FakeLLM({"action": "HOLD", "reason": "관망"}), _rule(), held=False, max_qty=3)
    assert v.action == "HOLD" and v.source == "AI" and v.reason == "관망"


def test_ai_cannot_override_lloyd():
    v = theo_ai(FakeLLM({"action": "BUY", "reason": "가자"}), _rule(risk_ok=False), held=False, max_qty=3)
    assert v.action == "HOLD"


def test_ai_cannot_sell_unheld():
    v = theo_ai(FakeLLM({"action": "SELL"}), _rule(), held=False, max_qty=3)
    assert v.action == "HOLD"


def test_ai_failure_falls_back_to_rules():
    rule = _rule()
    assert theo_ai(FakeLLM(None), rule, held=False, max_qty=3) is rule
    assert theo_ai(FakeLLM({"action": "MOON"}), rule, held=False, max_qty=3) is rule
