"""AI 판단에 쓰는 거시지표·뉴스 점수. 실패하면 None 을 돌려주고 그러면 기존 규칙만 쓴다."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


@dataclass
class Macro:
    score: float     # -1(주식에 불리) ~ +1(유리)
    summary: str


def macro_from(fx20: float, oil20: float, rate20_bp: float, vix: float, cpi_change: float | None = None) -> Macro:
    """20일 변화: 원/달러 %, 유가 %, 미국 10년물 bp. VIX 수준. 물가 발표 변화(%p)."""
    parts = [-_clamp(fx20 / 2), -_clamp(oil20 / 15) * 0.6, -0.7 if vix > 25 else 0.3 if vix < 15 else 0.0, -_clamp(rate20_bp / 35)]
    if cpi_change is not None:
        parts.append(-_clamp(cpi_change / 0.2))
    score = _clamp(sum(parts) / len(parts) * 1.6)
    return Macro(score, f"환율 20일 {fx20:+.1f}% · 유가 {oil20:+.1f}% · 美10년물 {rate20_bp:+.0f}bp · VIX {vix:.1f}")


def macro_snapshot(market) -> Macro | None:
    try:
        h = {k: market.history(t, period="3mo")["Close"].dropna() for k, t in
             (("fx", "KRW=X"), ("oil", "CL=F"), ("rate", "^TNX"), ("vix", "^VIX"))}
        chg = lambda s: (s.iloc[-1] / s.iloc[-21] - 1) * 100
        return macro_from(chg(h["fx"]), chg(h["oil"]), (h["rate"].iloc[-1] - h["rate"].iloc[-21]) * 100, float(h["vix"].iloc[-1]))
    except Exception as e:
        print(f"[거시지표 실패, 지수 흐름만 사용] {type(e).__name__}: {str(e)[:100]}")
        return None


def news_score(items: list[dict], today: date | None = None, days: int = 5) -> tuple[float, str] | None:
    """최근 며칠 뉴스 점수 합 (오래될수록 가볍게). items: [{'date','title','score'}]"""
    today = today or date.today()
    total, top, top_w = 0.0, "", 0.0
    for x in items:
        try:
            age = (today - date.fromisoformat(x["date"])).days
        except Exception:
            continue
        if 0 <= age < days and x.get("score"):
            w = (1 - age / days) * x["score"] * 0.6
            total += w
            if abs(w) > abs(top_w):
                top, top_w = x["title"], w
    return (_clamp(total), top) if top else None


def collect_news(names: dict[str, str]) -> dict[str, list[dict]]:
    """{심볼: 회사명} → {심볼: 최근 뉴스}. 구글 뉴스 헤드라인."""
    from .data.collect import google_news

    return {s: google_news(f'"{n}"', limit=15) for s, n in names.items()}


def recent(d: str, days: int = 10) -> bool:
    return date.fromisoformat(d) >= date.today() - timedelta(days=days)
