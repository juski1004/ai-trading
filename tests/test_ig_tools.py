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
