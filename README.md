# ai-trading

AI 6명이 실제 시세로 코스피·코스닥 주식을 분석하고 **가상 계좌**에서 자동매매하는 모의투자 게임.
진짜 돈은 쓰지 않는다. 투자 권유가 아니다.

| AI | 역할 |
|---|---|
| JOY | 시장·거시경제 (지수 흐름 + 환율·유가·금리·VIX) |
| OSCAR | 수급·뉴스 (거래량·가격 + 최근 뉴스·공시) |
| RAY | 차트 분석 (이동평균, MACD, RSI) |
| MILES | 진입 계획 (진입가·손절가·목표가·수량) |
| LLOYD | 리스크 점검 |
| THEO | 의견을 모아 최종 판정 (Gemini 무료 등급, 실패 시 규칙) |

## 게임 규칙 (`ai_trading/config.py`)
- 시작 자금 1,000만 원, 투자 기간 7~90일, 스윙 매매(하루 한 번)
- 분석 대상: 코스피·코스닥 대형주 78종목 (`ai_trading/data/universe.py`, `AI_UNIVERSE` 환경변수로 변경)
- 자동 손절 −5%, 자동 익절 +10%
- 한 종목 최대 20%, 최대 5종목, 하루 −3% 손실 시 그날 신규 매수 중지
- 수수료·거래세·미끄러짐 반영

## 화면: AI 트레이딩 아레나 (`web/index.html`)
증권사 HTS 같은 화면에서 **최근 90거래일 실제 데이터를 하루씩 다시 재생**하며 나와 AI 운용팀이 같은 1,000만 원으로 겨룬다.
- 일봉 차트, 보조지표 18종과 설정, 기술적 지표 요약, 호가 모양
- 경제지표(원/달러, 달러인덱스, WTI, 금, 미국 10년물, VIX, 한·미 물가, 한·미 기준금리)
- 뉴스·공시·경제 일정, 분기 실적·PER·PBR·ROE·부채비율·배당
- 코스피·코스닥 전 종목 검색 (차트와 대결은 분석 대상 종목만)
- 실전 AI 계좌: 엔진이 실제로 매매 중인 가상 계좌 기록
- 직원 사진은 AI로 만든 가상 인물이다.

## 데이터 (모두 무료)
| 항목 | 출처 | 키 |
|---|---|---|
| 시세·지수·환율·유가·금리·VIX | 야후 파이낸스 (15~20분 지연) | 필요 없음 |
| 종목 목록 | KRX 상장법인목록(KIND) | 필요 없음 |
| 분기 실적·자본·부채 | 야후 파이낸스 (발표일은 분기 말+30일로 추정) | 필요 없음 |
| 뉴스 헤드라인 | 구글 뉴스 RSS (제목·링크만) | 필요 없음 |
| 미국 물가·기준금리 | FRED | `FRED_API_KEY` (없으면 공개 CSV) |
| 한국 물가·기준금리 | 한국은행 ECOS | `ECOS_API_KEY` (없으면 최근 10건만) |
| 공시 | DART OpenAPI | `DART_API_KEY` (없으면 공시 생략) |

키는 **Settings → Secrets and variables → Actions → New repository secret** 에 위 이름으로 넣는다. 화면이나 커밋에는 절대 들어가지 않는다.

## 자동 실행 (`.github/workflows/trade.yml`)
- 평일 15:00 KST: 매매 사이클 (`cycle`), 판정은 `game/verdicts.json`
- 평일 16:20 KST: 화면 데이터 갱신 (`data`) → 화면과 데이터를 `site` 브랜치에 덮어써서 올림 (기록이 쌓이지 않음)
- 수동: Actions → "AI 모의투자 게임" → Run workflow → `start` / `cycle` / `report` / `data`

## 실행
```bash
pip install -r requirements.txt
python -m pytest
python -m ai_trading.data.export --out web/data   # 화면 데이터 만들기 (5분 정도)
python -m http.server 8765 --directory web        # http://localhost:8765 에서 화면 보기
python -m ai_trading.team 005930.KS               # AI 6명 분석
python -m ai_trading.run start --days 30
python -m ai_trading.run cycle
python -m ai_trading.run report
```
