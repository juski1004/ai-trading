import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import viral_rank, caption_check


def test_viral_rank_uses_own_median():
    rows = [{"account": "a", "median": "5,000", "views": "400000", "hook": "x"},
            {"account": "b", "median": "350000", "views": "400000", "hook": "y"}]
    r = viral_rank.rank(rows)
    assert r[0]["account"] == "a" and r[0]["mult"] > 3 and r[1]["mult"] < 1.5


def test_caption_check_flags():
    bad = "\n".join(["첫 줄 " + "가" * 80, "선착순 #a #b"])
    out = "\n".join(caption_check.check(bad))
    assert "주의 첫 줄" in out and "선착순" in out and "해시태그 2개" in out
    ok = "더 보기 눌러 분석 확인\n#1 #2 #3 #4 #5 #6 #7 #8"
    assert "주의" not in "\n".join(caption_check.check(ok))


def test_caption_check_overlap():
    out = "\n".join(caption_check.check("더 보기\n#주식 #주식공부 #a #b #c #d #e #f"))
    assert "겹침(" in out and "#주식⊂#주식공부" in out


def test_generated_tags_have_8_and_no_overlap():
    from ai_trading import reel
    from ai_trading.data import cards, termcards
    from ai_trading.data.hashtags import overlaps
    lines = [termcards.term_tags("PER", "주가수익비율"), termcards.term_tags("경제지표 CPI", "소비자물가지수"), reel.APP_TAGS,
             cards._tags(cards.BIG_TAGS, ["장마감", "퇴근길", "오늘의시황", "삼성전자"], ["시장브리핑"])]
    for l in lines:
        assert len(l.split()) == 8 and not overlaps(l.split()), l


def test_premade_captions_no_overlap():
    import json, re
    from ai_trading.data.hashtags import overlaps
    root = Path(__file__).resolve().parents[1] / "web" / "content"
    for f in ["termcards/termcards.json", "reels/reels.json"]:
        for it in json.loads((root / f).read_text(encoding="utf-8"))["items"]:
            tags = re.findall(r"#\S+", it["caption"])
            assert len(tags) == 8 and not overlaps(tags), (f, it["date"], tags)


def test_first_comment_gets_same_tags():
    import ig_publish
    cap = "본문\n\n#주식 #재테크 #경제 #증시 #VIX #공포지수 #용어정리 #주말공부"
    assert ig_publish.tags_of(cap) == "#주식 #재테크 #경제 #증시 #VIX #공포지수 #용어정리 #주말공부"
    assert ig_publish.tags_of("태그 없음") == ""
