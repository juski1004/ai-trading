"""음성용 숫자 읽기 (2026-11-19 사용자: "로봇 음성 일번 이번 삼번 이렇게 읽어야지").
TTS가 '1번'을 '한 번'·'하나 번'처럼 읽는 것을 막으려고, 음성에 넘기기 전에 한자어 숫자로 바꾼다.
- 1번 → 일 번, 12번 → 십이 번 ('번째'는 그대로: 첫 번째·두 번째는 고유어로 읽어야 맞음)
- 1·2·3 / 1, 2, 3 처럼 번호를 나열한 것 → 일, 이, 삼
"""
import re

_D = "영일이삼사오육칠팔구"


def sino(n: int) -> str:
    if n == 0: return "영"
    out = ""
    for unit, name in ((1000, "천"), (100, "백"), (10, "십")):
        q, n = divmod(n, unit)
        if q: out += ("" if q == 1 else _D[q]) + name
    return out + (_D[n] if n else "")


def speak(text: str) -> str:
    text = re.sub(r"(?<![\d.])(\d{1,4})\s*번(?!째)", lambda m: sino(int(m.group(1))) + " 번", text)
    text = re.sub(r"(?<![\d.])\d(?:\s*[·,]\s*\d)+(?![\d.])",
                  lambda m: ", ".join(_D[int(x)] for x in re.findall(r"\d", m.group(0))), text)
    return text
