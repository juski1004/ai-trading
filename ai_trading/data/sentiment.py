"""뉴스 제목으로 호재/악재를 가늠하는 간단한 단어 규칙. (+1 호재, -1 악재, 0 중립)"""
from __future__ import annotations

POSITIVE = ("수주", "공급 계약", "공급계약", "상향", "사상 최대", "사상 최고", "최대 실적", "흑자", "호실적", "급등",
            "신고가", "자사주", "소각", "승인", "출시", "서프라이즈", "호조", "상승", "반등", "순매수", "증가", "돌파")
NEGATIVE = ("하향", "적자", "급락", "리콜", "소송", "피소", "유상증자", "블록딜", "부진", "쇼크", "손실", "감소",
            "우려", "제재", "하락", "순매도", "악화", "횡령", "배임", "상장폐지", "거래정지")


def headline_score(title: str) -> int:
    p = sum(w in title for w in POSITIVE)
    n = sum(w in title for w in NEGATIVE)
    return 1 if p > n else -1 if n > p else 0
