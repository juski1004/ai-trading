"""장마감 카드 5장 → 세로 릴스 (1080x1920, 약 16초, 배경음).
2026-10-29 사용자: "조회수 너무 안 나오니 내일은 릴스 한 편 만들어 봐" — 매일 만들어 두기만 하고, 올리는 건 사용자가 정한 날만.
- 카드 그대로(숫자·문구 추가 없음) 가운데, 위에 날짜 제목, 아래에 댓글 '연구소' 안내
- 배경음: web/app/bgm/main.mp3 (앱에 쓰는 자체 제작 음악)
결과: <web>/data/cards/reel.mp4, reel_cover.jpg
실행: python -m ai_trading.data.cards_reel web
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from ai_trading.data.cards import INK, UP, WHITE, _font as F, theme_of

W, H, SEC, FADE = 1080, 1920, 3.4, 0.4


def build(web: Path) -> Path | None:
    web = Path(web); cd = web / "data" / "cards"
    info = json.loads((cd / "cards.json").read_text(encoding="utf-8"))
    date = info["date"]; md = f"{int(date[5:7])}월 {int(date[8:])}일"; th = theme_of(date)
    tmp = Path(tempfile.mkdtemp())
    frames = []
    for i, rel in enumerate(info["images"]):
        im = Image.new("RGB", (W, H), th["paper"]); d = ImageDraw.Draw(im)
        d.text((W // 2, 150), f"{md} 주식 장마감 1분 요약", font=F("ExtraBold", 54), fill=INK, anchor="mm")
        d.text((W // 2, 222), "오늘 가장 크게 움직인 종목, 이유까지", font=F("Medium", 34), fill=(112, 116, 128), anchor="mm")
        card = Image.open(cd / Path(rel).name).convert("RGB").resize((1000, 1250))
        im.paste(card, (40, 300))
        d.rounded_rectangle((90, 1610, 990, 1730), 30, fill=UP)
        d.text((W // 2, 1650), "실전 데이터 모의투자 앱 선착순 무료 배포", font=F("ExtraBold", 38), fill=WHITE, anchor="mm")
        d.text((W // 2, 1698), "댓글에 '연구소' 남겨주세요", font=F("Bold", 32), fill=WHITE, anchor="mm")
        d.text((W // 2, 1790), f"{i + 1} / {len(info['images'])}", font=F("Bold", 30), fill=(112, 116, 128), anchor="mm")
        p = tmp / f"f{i}.png"; im.save(p); frames.append(p)
        if i == 0: im.convert("RGB").save(cd / "reel_cover.jpg", quality=90)
    n = len(frames); total = n * SEC - (n - 1) * FADE
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in frames: args += ["-loop", "1", "-t", str(SEC), "-framerate", "30", "-i", str(p)]
    bgm = web / "app" / "bgm" / "main.mp3"
    if bgm.exists(): args += ["-i", str(bgm)]
    chain, last = [], "0:v"
    for k in range(1, n):
        out = f"x{k}"; chain.append(f"[{last}][{k}:v]xfade=transition=slideleft:duration={FADE}:offset={k * (SEC - FADE):.2f}[{out}]"); last = out
    chain.append(f"[{last}]format=yuv420p[v]")
    args += ["-filter_complex", ";".join(chain), "-map", "[v]"]
    if bgm.exists(): args += ["-map", f"{n}:a", "-af", f"afade=t=in:d=0.5,afade=t=out:st={total - 1.2:.2f}:d=1.2", "-c:a", "aac", "-b:a", "128k"]
    args += ["-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", "30", "-movflags", "+faststart", str(cd / "reel.mp4")]
    subprocess.run(args, check=True)
    return cd / "reel.mp4"


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "web")))
