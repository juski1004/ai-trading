# ai-trading

AI 6명이 실제 시세로 국내·미국 주식을 분석하고 **가상 계좌**에서 자동매매하는 모의투자 게임.
진짜 돈은 쓰지 않는다.

| AI | 역할 |
|---|---|
| JOY | 시장 리포트 |
| OSCAR | 거래소 데이터 |
| RAY | 차트 분석 |
| MILES | 진입 계획 |
| LLOYD | 리스크 점검 |
| THEO | 의견을 모아 최종 판정 |

## 게임 규칙 (`ai_trading/config.py`)
- 시작 자금 1,000만 원, 투자 기간 7~90일
- 국내(`.KS`/`.KQ`) + 미국 주식, 미국 주식은 실제 환율로 원화 환산
- 자동 손절 −5%, 자동 익절 +10%
- 한 종목 최대 20%, 최대 5종목, 하루 −3% 손실 시 그날 신규 매수 중지
- 수수료·거래세·미끄러짐 반영
- 시세: 야후 파이낸스 (15~20분 지연)

## 진행 상황
- [x] 가상 계좌 엔진 (`ai_trading/broker.py`)
- [x] AI 6명 분석: 무료 규칙 기반 (`ai_trading/agents.py`, `ai_trading/team.py`)
- [x] 무료 AI 연결: THEO가 구글 Gemini 무료 등급으로 최종 판정 (`ai_trading/llm.py`)
  - `GEMINI_API_KEY` 환경변수가 없거나 실패하면 규칙 기반으로 자동 전환
  - AI도 LLOYD의 거절을 무시할 수 없음 (코드에서 강제)
- [ ] 자동 실행 스케줄러
- [ ] 결과 리포트

## 실행
```bash
pip install -r requirements.txt
python -m pytest
python -m ai_trading.team            # 관심 종목 전체를 AI 6명이 분석
python -m ai_trading.team AAPL 005930.KS
```
