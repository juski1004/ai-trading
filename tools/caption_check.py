"""캡션 첫 줄 점검 (2026-11-01, instagram-agent-skill ig-caption 아이디어, MIT).
피드에는 캡션의 처음 일부만 보이고 나머지는 '더 보기' 뒤에 숨는다. 한글은 영어보다 폭이 넓어 보이는 글자 수를 약 70자로 잡는다(추정).
확인: ① 첫 줄이 보이는 구간 안에서 끝나는가 ② '더 보기' 유도가 그 구간 안에 있는가 ③ 해시태그가 8개(큰4+작은4)인가 ④ 금지어(선착순) 없는가
usage: python3 tools/caption_check.py caption.txt
"""
from __future__ import annotations
import re, sys
VISIBLE = 70

def check(text: str) -> list[str]:
    t = text.strip(); first = t.splitlines()[0] if t else ""
    seen = t[:VISIBLE]; out = []
    out.append(("OK " if len(first) <= VISIBLE else "주의 ") + f"첫 줄 {len(first)}자 (보이는 구간 약 {VISIBLE}자)")
    more = "더 보기" in seen or "더보기" in seen
    out.append("OK '더 보기' 유도가 보이는 구간 안에 있음" if more else "주의 '더 보기' 유도가 보이는 구간 안에 없음 (첫 두 줄 안에 넣기)")
    tags = re.findall(r"#\S+", t)
    out.append(("OK " if len(tags) == 8 else "주의 ") + f"해시태그 {len(tags)}개 (큰4+작은4 = 8개)")
    if "선착순" in t: out.append("주의 '선착순' 문구 있음 (사용자 지시로 금지)")
    out.append("--- 화면에 보이는 부분 ---\n" + seen + ("…더 보기" if len(t) > VISIBLE else ""))
    return out

if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    print("\n".join(check(open(sys.argv[1], encoding="utf-8").read())))
