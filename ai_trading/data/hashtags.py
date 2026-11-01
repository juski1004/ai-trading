"""해시태그 규칙 (2026-10-30·11-01 사용자 지시): 큰 태그 4개 + 작은 태그 4개, 서로 겹치면 안 된다.
'겹침' = 한 태그가 다른 태그 안에 통째로 들어 있는 경우 (#주식 ⊂ #주식공부·#주식용어·#퇴근길주식). 이런 건 하나만 남긴다.
"""
from __future__ import annotations


def overlaps(tags: list[str]) -> list[tuple[str, str]]:
    t = [x.lstrip("#").lower() for x in tags]
    return [(tags[i], tags[j]) for i in range(len(t)) for j in range(len(t)) if i != j and t[i] and t[i] in t[j] and (t[i] != t[j] or i < j)]


def line(big: list[str], small: list[str], pool: list[str] = (), n_small: int = 4) -> str:
    """큰 4 + 작은 4 해시태그 줄. small 후보 중 큰 태그·앞선 태그와 겹치는 건 건너뛰고 pool 에서 채운다."""
    out = [b.lstrip("#") for b in big]
    assert len(out) == 4 and not overlaps(out), f"큰 태그가 겹침: {big}"
    chosen: list[str] = []
    for c in [*small, *pool]:
        c = c.lstrip("#").replace(" ", "").replace("/", "")
        if not c or len(chosen) == n_small: continue
        if not overlaps(["#" + x for x in out + chosen + [c]]):
            chosen.append(c)
    assert len(chosen) == n_small, f"작은 태그 {len(chosen)}개뿐: {small}"
    return " ".join("#" + x for x in out + chosen)
