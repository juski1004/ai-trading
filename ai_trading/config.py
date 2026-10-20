"""게임 규칙. 숫자는 여기서만 바꾸면 된다."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GameRules:
    starting_cash_krw: float = 10_000_000  # 시작 자금 1,000만 원
    min_days: int = 7                      # 투자 기간 최소 1주
    max_days: int = 90                     # 투자 기간 최대 3개월

    # 자동 매도 기준 (매수 평균가 대비, 현지 통화 가격 기준)
    stop_loss_pct: float = -5.0
    take_profit_pct: float = 10.0

    # 안전장치
    max_position_pct: float = 20.0   # 한 종목 최대 비중 (총자산 대비)
    max_positions: int = 5           # 동시 보유 최대 종목 수
    daily_loss_limit_pct: float = -3.0  # 하루 손실이 이보다 크면 그날 신규 매수 중지

    # 비용 (실제와 비슷한 근사치)
    kr_commission_pct: float = 0.015  # 국내 매수/매도 수수료
    kr_sell_tax_pct: float = 0.20     # 국내 매도 거래세
    us_commission_pct: float = 0.25   # 미국 매수/매도 수수료
    slippage_pct: float = 0.05        # 체결 가격 미끄러짐

    # AI 분석 주기 (분)
    cycle_minutes: int = 30
