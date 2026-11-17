"""주식연구소 주간 릴스 (2026-11-17 사용자: "평일 홍보 2회, 홍보에 퀴즈 / 주말에 주식 공부 용어 정리에 퀴즈 정답 공개")

- promo  (화·목 17:30): 기능 홍보 릴스(약 15초, reel.py 'app' — 기능 5개를 차례로) + 차트 퀴즈 1문제(quiz.py)
                       → <web>/data/reel/reel.mp4·reel.json (올리기: ig_publish.py reel)
- study  (토 12:00):   주식 용어 릴스(reel.py 'word') + 그 주 화·목 퀴즈 정답 공개(quiz.render_answers)
                       → <web>/data/study/reel.mp4·reel.json (올리기: ig_publish.py study)
실행: python -m ai_trading.weekly_reels web promo|study YYYY-MM-DD   (전날 데이터 실행 때 그날 날짜로 미리 만듦)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ai_trading import reel as RL
from ai_trading.data import quiz as QZ


def concat(videos: list[Path], out: Path) -> None:
    """세로 1080x1920·30fps 영상들을 소리까지 이어 붙임 (다시 인코딩)."""
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for v in videos: args += ["-i", str(v)]
    n = len(videos)
    fl = "".join(f"[{i}:v]fps=30,scale=1080:1920,setsar=1[v{i}];[{i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}];" for i in range(n))
    fl += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    args += ["-filter_complex", fl, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    subprocess.run(args, check=True)


def _before_tags(caption: str, extra: str) -> str:
    """캡션 맨 끝 해시태그 줄 앞에 문단 하나 끼워 넣기."""
    head, sep, tags = caption.rpartition("\n\n")
    return f"{head}\n\n{extra}{sep}{tags}" if sep and tags.lstrip().startswith("#") else f"{caption}\n\n{extra}"


def promo(web: Path, at: str) -> dict | None:
    web = Path(web); data = web / "data"; out = data / "reel"
    info = RL.build(web, "app", at, out)
    if not info: return None
    with tempfile.TemporaryDirectory() as td:
        q = QZ.render(web, at, Path(td) / "quiz")
        if q:
            tmp = Path(td) / "joined.mp4"
            concat([out / "reel.mp4", Path(td) / "quiz" / "quiz.mp4"], tmp)
            shutil.move(str(tmp), out / "reel.mp4")
            info["quiz"] = {k: q[k] for k in ("sym", "name", "up", "chg", "hint", "period")}
            info["caption"] = _before_tags(info["caption"], "🧩 오늘의 차트 퀴즈: 이 종목, 한 달 뒤 오를까? 내릴까?\n"
                                           f"💡 힌트: {q['hint']}\n👇 댓글로 1(오른다) 또는 2(내린다)! 정답은 이번 주 토요일 12시에 공개해요")
    (out / "reel.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


def study(web: Path, at: str) -> dict | None:
    web = Path(web); data = web / "data"; out = data / "study"
    if out.exists(): shutil.rmtree(out)
    info = RL.build(web, "word", at, out)
    if not info: return None
    with tempfile.TemporaryDirectory() as td:
        ans = Path(td) / "answers.mp4"
        items = QZ.render_answers(web, at, ans)
        if items:
            tmp = Path(td) / "joined.mp4"
            concat([out / "reel.mp4", ans], tmp)
            shutil.move(str(tmp), out / "reel.mp4")
            day = "월화수목금토일"
            lines = [f"🧩 {QZ.dt.date.fromisoformat(h['date']).month}/{QZ.dt.date.fromisoformat(h['date']).day}"
                     f"({day[QZ.dt.date.fromisoformat(h['date']).weekday()]}) 퀴즈 정답: {h['name']} → 한 달 뒤 "
                     f"{'+' if h['chg'] > 0 else ''}{h['chg']}% ({'1번 오른다' if h['up'] else '2번 내린다'})" for h in items]
            info["answers"] = [h["date"] for h in items]
            info["caption"] = _before_tags(info["caption"], "이번 주 차트 퀴즈 정답 공개 🎉\n" + "\n".join(lines))
    info["video"], info["cover"] = "study/reel.mp4", "study/cover.jpg"
    (out / "reel.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


if __name__ == "__main__":
    a = sys.argv[1:]
    web, what, at = Path(a[0]), a[1], a[2]
    r = (promo if what == "promo" else study)(web, at)
    print(json.dumps(r, ensure_ascii=False, indent=1) if r else "만들 것 없음")
