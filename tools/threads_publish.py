"""인스타에 올린 것을 스레드(Threads)에도 같이 올리기 (2026-10-30 사용자 지시: 노출 늘리기 1번).

토큰: 환경변수 THREADS_TOKEN (ai.tooja.lab 스레드 계정 장기 토큰, 60일 → check 때 연장).
없으면 조용히 건너뛰고, 실패해도 인스타 게시는 그대로 성공으로 둔다.
스레드 규칙: 글 500자 이내, 해시태그(주제 태그)는 1개만 붙는다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"
TOKEN = os.environ.get("THREADS_TOKEN", "").strip()
TOPIC = "#주식"


def _call(method: str, path: str, **params) -> dict:
    params["access_token"] = TOKEN
    url = path if path.startswith("http") else f"{API}/{path}"
    data = None
    if method == "GET": url += "?" + urllib.parse.urlencode(params)
    else: data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:  # 토큰은 출력하지 않음
        raise RuntimeError(f"스레드 API 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def text_of(caption: str) -> str:
    """인스타 캡션 → 스레드 글: 해시태그 줄을 빼고 500자 안으로, 주제 태그 1개."""
    lines = [l for l in caption.splitlines() if not l.strip().startswith("#")]
    # 스레드 댓글로는 DM 자동 발송이 안 되니 인스타로 안내
    lines = ["👉 모의투자 앱은 인스타 @ai.tooja.lab 게시물에 댓글 '연구소' 남기면 DM으로 보내 드려요" if "'연구소'" in l else l for l in lines]
    body = "\n".join(lines).strip()
    body = " ".join(w for w in body.split(" ") if not w.startswith("#"))  # 줄 안 해시태그도 빼기
    room = 500 - len(TOPIC) - 2
    if len(body) > room: body = body[:room - 1].rstrip() + "…"
    return f"{body}\n\n{TOPIC}"


def _wait(cid: str, minutes: int = 6) -> None:
    end = time.time() + minutes * 60
    while time.time() < end:
        st = _call("GET", cid, fields="status,error_message")
        if st.get("status") == "FINISHED": return
        if st.get("status") in ("ERROR", "EXPIRED"): raise RuntimeError(f"스레드 미디어 처리 실패: {st}")
        time.sleep(5)
    raise RuntimeError("스레드 미디어 처리 시간 초과")


def _already(text: str) -> bool:
    first = text.strip().splitlines()[0].strip()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=20)
    for m in _call("GET", "me/threads", fields="text,timestamp", limit=10).get("data", []):
        ts = dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        if ts >= since and (m.get("text") or "").strip().splitlines()[:1] == [first]: return True
    return False


def mirror(caption: str, images: list[str] | None = None, video: str | None = None) -> str:
    """images: 공개 이미지 주소들(캐러셀), video: 공개 동영상 주소. 결과 한 줄을 돌려준다."""
    if not TOKEN: return "[스레드] 토큰 없음 → 건너뜀"
    try:
        text = text_of(caption)
        if _already(text): return "[스레드] 이미 올림 → 건너뜀"
        if video:
            cid = _call("POST", "me/threads", media_type="VIDEO", video_url=video, text=text)["id"]
        elif images and len(images) > 1:
            kids = [_call("POST", "me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"] for u in images[:20]]
            for k in kids: _wait(k, 3)
            cid = _call("POST", "me/threads", media_type="CAROUSEL", children=",".join(kids), text=text)["id"]
        elif images:
            cid = _call("POST", "me/threads", media_type="IMAGE", image_url=images[0], text=text)["id"]
        else:
            cid = _call("POST", "me/threads", media_type="TEXT", text=text)["id"]
        _wait(cid)
        tid = _call("POST", "me/threads_publish", creation_id=cid)["id"]
        link = _call("GET", tid, fields="permalink").get("permalink", "")
        return f"[스레드] 게시 완료: {link}"
    except Exception as e:  # 스레드가 실패해도 인스타 게시는 성공으로
        return f"[스레드 실패] {e}"


def refresh() -> str:
    """장기 토큰 연장 (check 때). 남은 기간을 돌려준다."""
    if not TOKEN: return "[스레드] 토큰 없음"
    try:
        r = _call("GET", f"https://graph.threads.net/refresh_access_token", grant_type="th_refresh_token")
        return f"[스레드] 토큰 연장 · 남은 기간 약 {int(r.get('expires_in', 0)) // 86400}일"
    except Exception as e:
        return f"[스레드 토큰 확인 실패] {e}"
