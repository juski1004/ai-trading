import json
import shutil
from pathlib import Path

from ai_trading.data.archive import build

FIX = {
    "scores.json": {"date": "2026-10-23", "market": {"kospi": {"v": 5550.3, "chg": 0.3}, "kosdaq": {"v": 751.69, "chg": -1.62}, "usdkrw": {"v": 1326.0, "chg": 0.1}},
                    "stocks": {"A.KS": {"name": "가나", "chg": 7.27, "price": 1000}, "B.KS": {"name": "다라", "chg": -7.06, "price": 2000}, "C.KS": {"name": "마바", "chg": 0.5, "price": 3000}}},
    "outlook.json": {"facts": {"코스피": {"1일": 0.3, "5일": -2.08, "20일": -20.8}, "코스닥": {"1일": -1.62, "5일": -5.42, "20일": -10.11},
                               "오늘_시장수급_억원": {"KOSPI": {"frg": -9811, "org": 8682, "ind": 422}}, "WTI_20일%": 11.75, "미국10년물": 4.99, "VIX": 19.5},
                     "lines": ["기관·외국인 순매수 8,682억 원"]},  # AI 문장 — 아카이브에 들어가면 안 됨
    "why.json": {"date": "2026-10-23", "sym": {"A.KS": {"line": "실적이 좋았어요", "tone": "호재"}}},
}


def _web(tmp: Path) -> Path:
    d = tmp / "web" / "data"; d.mkdir(parents=True)
    for k, v in FIX.items():
        (d / k).write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    return tmp / "web"


def test_archive_page_and_index(tmp_path):
    web = _web(tmp_path)
    r = build(web)
    assert r == {"date": "2026-10-23", "count": 1}
    page = (web / "archive" / "2026-10-23.html").read_text(encoding="utf-8")
    assert "10월 23일 장마감 요약" in page and "가나" in page and "실적이 좋았어요" in page
    assert "-9,811억 원" in page            # 수급은 데이터 숫자 그대로
    assert "기관·외국인 순매수" not in page   # AI 시황 문장은 쓰지 않음
    assert "권합니다" not in page and "추천" not in page
    idx = json.loads((web / "archive" / "index.json").read_text(encoding="utf-8"))
    assert [x["date"] for x in idx] == ["2026-10-23"]
    assert "2026-10-23.html" in (web / "archive" / "sitemap.xml").read_text(encoding="utf-8")


def test_archive_accumulates_and_reruns_same_day(tmp_path):
    web = _web(tmp_path)
    build(web)
    s = json.loads((web / "data" / "scores.json").read_text(encoding="utf-8")); s["date"] = "2026-10-26"
    (web / "data" / "scores.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    build(web); build(web)  # 같은 날 두 번 돌아도 한 편
    idx = json.loads((web / "archive" / "index.json").read_text(encoding="utf-8"))
    assert [x["date"] for x in idx] == ["2026-10-26", "2026-10-23"]
    assert '2026-10-23.html">‹ 2026-10-23' in (web / "archive" / "2026-10-26.html").read_text(encoding="utf-8")
