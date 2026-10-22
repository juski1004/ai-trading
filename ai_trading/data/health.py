"""화면 데이터 자동 점검. 비거나 오래된 항목을 찾아 알림용 글을 만든다.

  python -m ai_trading.data.health web/data          점검 결과를 출력 (문제 있으면 첫 줄이 '문제 N건')

자동 실행에서는 문제가 있으면 GitHub 이슈를 열어 메일로 알리고, 다 고쳐지면 이슈를 닫는다.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path


def _load(d: Path, name: str, default=None):
    try:
        return json.loads((d / name).read_text(encoding="utf-8"))
    except Exception:
        return default


def check(d: Path, today: date | None = None) -> tuple[list[str], list[str]]:
    """(문제, 참고) 목록."""
    today = today or date.today()
    bad, note = [], []
    key = lambda k: bool(os.getenv(k))
    mk = _load(d, "market.json")
    if not mk:
        return ["market.json 이 없습니다. 시세 수집이 통째로 실패했습니다."], note
    last = date.fromisoformat(mk["dates"][-1])
    if (today - last).days > 5:
        bad.append(f"시세가 {last} 이후로 갱신되지 않았습니다 (야후 파이낸스 확인 필요).")
    n = len(mk.get("stocks", {}))
    if n < 70:
        bad.append(f"분석 대상 시세가 {n}종목뿐입니다 (78종목 기대).")
    for k, label in (("usdkrw", "원/달러"), ("dxy", "달러인덱스"), ("wti", "WTI 유가"), ("gold", "금"),
                     ("us10y", "미국 10년물"), ("vix", "VIX"), ("kospi", "코스피"), ("kosdaq", "코스닥")):
        s = mk.get("macro", {}).get(k) or []
        if sum(v is not None for v in s) < 100:
            bad.append(f"경제지표 '{label}' 값이 비었습니다.")
    rel = mk.get("releases", {})
    for k, label, env in (("us_cpi", "미국 물가", "FRED_API_KEY"), ("kr_cpi", "한국 물가", "ECOS_API_KEY"),
                          ("fed", "미국 기준금리", "FRED_API_KEY"), ("bok", "한국 기준금리", "ECOS_API_KEY")):
        if len(rel.get(k) or []) < (3 if "cpi" in k else 1):
            (bad if key(env) else note).append(f"{label} 자료가 비었습니다" + (" (키 만료·오류 가능, 한국은행 ECOS 키는 만료일 확인)" if env == "ECOS_API_KEY" else "") + ".")
    fin = _load(d, "fin.json", {})
    nq = sum(1 for v in fin.values() if v.get("quarters"))
    ne = sum(1 for v in fin.values() if v.get("est"))
    if nq < 60:
        bad.append(f"분기 실적이 {nq}종목에만 있습니다.")
    if ne < 30:
        bad.append(f"증권사 예상 실적이 {ne}종목에만 있습니다.")
    news = _load(d, "news.json", {"eco": [], "sym": {}})
    tot = sum(len(v) for v in news.get("sym", {}).values())
    dart = sum(1 for v in news.get("sym", {}).values() for x in v if x.get("src") == "DART")
    if len(news.get("eco", [])) < 5 or tot < 200:
        bad.append(f"뉴스가 적습니다 (경제 {len(news.get('eco', []))}건, 종목 {tot}건, 구글 뉴스 확인 필요).")
    if key("DART_API_KEY") and dart == 0:
        bad.append("DART 공시가 0건입니다 (DART 키 확인 필요).")
    fl = _load(d, "flows.json")
    if not fl:
        bad.append("수급 자료(flows.json)가 없습니다 (네이버 증권 주소가 바뀌었을 수 있음).")
    else:
        nf = sum(1 for v in fl.get("stocks", {}).values() if v)
        if nf < 60:
            bad.append(f"수급이 {nf}종목에만 있습니다 (네이버 증권 확인 필요).")
        if not fl.get("market", {}).get("KOSPI"):
            bad.append("코스피 시장 수급이 비었습니다.")
    ol = _load(d, "outlook.json")
    if not ol:
        bad.append("오늘의 시장 전망이 없습니다.")
    elif key("GEMINI_API_KEY") and ol.get("source") != "AI":
        bad.append("시장 전망을 AI(Gemini)가 쓰지 못하고 자동 문장으로 대신했습니다 (Gemini 키·한도·모델 확인).")
    summ = _load(d, "summary.json", {})
    if key("GEMINI_API_KEY") and not summ:
        note.append("뉴스 AI 요약이 0종목입니다 (Gemini 무료 한도일 수 있음).")
    if not (d / "scores.json").exists():
        bad.append("앱용 AI 점수(scores.json)가 없습니다.")
    meta = _load(d, "meta.json", {})
    w = meta.get("warnings") or []
    if w:
        note.append(f"수집 중 경고 {len(w)}건: " + " / ".join(w[:6]))
    return bad, note


def report(d: Path) -> str:
    bad, note = check(d)
    lines = [f"문제 {len(bad)}건" if bad else "문제 없음", ""]
    if bad:
        lines += ["### 고쳐야 할 것"] + [f"- {x}" for x in bad] + [""]
    if note:
        lines += ["### 참고"] + [f"- {x}" for x in note] + [""]
    lines.append("화면은 문제가 있는 칸만 비고 나머지는 계속 갱신됩니다.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(Path(sys.argv[1] if len(sys.argv) > 1 else "web/data")))
