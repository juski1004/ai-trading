# 미리 만든 게시물 (2026-10-26 사용자: "만들 수 있는 건 지금 만들어 놓고 업로드만 맞춰서")
- termcards/<날짜>/1~5.jpg + termcards.json: 주말(토·일) 용어 정리 카드뉴스 22개 (2026-10-31 ~ 2027-01-10). 실제 숫자는 10/26 종가 기준.
- reels/<날짜>/reel.mp4·cover.jpg + reels.json: 금요일 앱 광고 릴스 6개 (2026-10-30 ~ 12-04).
- 게시 순서: 그날 데이터 실행이 새로 만든 data/termcards·data/reel(최신 숫자)이 있으면 그것, 없으면 여기 미리 만든 것.
- 다시 만들기: python -m ai_trading.data.termcards <data폴더> <날짜…> / ai_trading.reel.build(web, "app", at=<날짜>, out=<폴더>)
