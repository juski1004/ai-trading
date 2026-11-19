import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ko_numbers import speak  # noqa: E402


def test_numbered_items_read_sino_korean():
    assert speak("정답은 2번이야") == "정답은 이 번이야"
    assert speak("1번, 3번 말고 12번") == "일 번, 삼 번 말고 십이 번"
    assert speak("댓글로 1·2·3!") == "댓글로 일, 이, 삼!"


def test_ordinals_and_other_numbers_untouched():
    assert speak("첫 번째. 두 번째 영상") == "첫 번째. 두 번째 영상"
    assert speak("2025년 11월, 1,000달러") == "2025년 11월, 1,000달러"
