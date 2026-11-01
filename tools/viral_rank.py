"""참고 릴스 순위: 조회수가 아니라 '그 계정의 평소 중간값 대비 몇 배'로 매긴다 (2026-11-01, instagram-agent-skill ig-viral 아이디어, MIT).
입력: TSV 파일(탭으로 구분, 첫 줄은 머리글) 열: account followers median views hook
  - median: 그 계정 최근 릴스 12개의 중간 조회수(눈대중 가능), hook: 첫 문장 그대로
출력: 배수 내림차순 표. 3배 이상만 '신호', 1.5배 미만은 그 계정의 평범한 날이라 배울 게 없다.
usage: python3 tools/viral_rank.py captured.tsv [--out swipe.md]
"""
from __future__ import annotations
import csv, sys

def rank(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        try:
            med, v = float(r["median"].replace(",", "")), float(r["views"].replace(",", ""))
        except (KeyError, ValueError):
            continue
        if med <= 0: continue
        out.append({**r, "mult": v / med})
    return sorted(out, key=lambda x: -x["mult"])

def table(rows: list[dict]) -> str:
    lines = ["| 순위 | 계정 | 조회수 | 평소 중간값 | 배수 | 판정 | 첫 문장 |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        m = r["mult"]; tag = "신호(따라 해볼 것)" if m >= 3 else "보통" if m >= 1.5 else "평범한 날(배울 것 없음)"
        lines.append(f"| {i} | @{r['account'].lstrip('@')} | {r['views']} | {r['median']} | {m:.1f}배 | {tag} | {r.get('hook','')} |")
    return "\n".join(lines)

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: raise SystemExit(__doc__)
    with open(a[0], encoding="utf-8", newline="") as f: rows = list(csv.DictReader(f, delimiter="\t"))
    t = table(rank(rows)); print(t)
    if "--out" in a: open(a[a.index("--out") + 1], "w", encoding="utf-8").write(t + "\n\n(공식 이름 붙이기: marketing/instagram/훅공식.md. 영상 자체가 아니라 첫 문장 구조와 길이만 참고, 계정 출처 표기)\n")
