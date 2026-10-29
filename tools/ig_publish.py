"""인스타그램 공식 API로 직접 올리기 (미라 대신, 무료).

사이트(GitHub Pages)에 이미 공개된 카드·릴스 파일 주소를 인스타에 넘겨 게시한다.
토큰: 환경변수 IG_ACCESS_TOKEN
 - 통합 로그인(시스템 사용자 토큰, 만료 없음) → graph.facebook.com + 인스타 계정 ID (IG_USER_ID, 없으면 자동으로 찾음)
 - Instagram 로그인 토큰(IG로 시작) → graph.instagram.com + me

사용:
  python tools/ig_publish.py check                 # 토큰·계정 확인, 남은 기간 표시 (게시 안 함)
  python tools/ig_publish.py cards  [--tags "#a #b"] # 오늘 장마감 카드 5장 (캐러셀)
  python tools/ig_publish.py cardsreel [--tags ..]  # 장마감 카드로 만든 릴스
  python tools/ig_publish.py term [--date YYYY-MM-DD]  # 주말 용어 카드
  python tools/ig_publish.py reel                   # 앱 소개 릴스
공통: --force (날짜가 오늘이 아니어도, 이미 올린 것 같아도 올림)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IGLOGIN = TOKEN.startswith("IG")
API = "https://graph.instagram.com/v23.0" if IGLOGIN else "https://graph.facebook.com/v23.0"
_UID: list[str] = []


def uid() -> str:
    """게시할 인스타 계정 ID. Instagram 로그인 토큰은 me, 통합 로그인은 실제 ID."""
    if IGLOGIN: return "me"
    if not _UID:
        u = os.environ.get("IG_USER_ID", "").strip()
        if not u:  # 토큰에 연결된 페이지 → 인스타 비즈니스 계정 순으로 찾기
            for pg in call("GET", "me/accounts", fields="instagram_business_account{id,username}").get("data", []):
                ib = pg.get("instagram_business_account")
                if ib: u = ib["id"]; break
        if not u:
            raise SystemExit("인스타 계정 ID를 못 찾음 → GitHub 비밀값 IG_USER_ID 에 넣어 주세요")
        _UID.append(u)
    return _UID[0]
SITE = os.environ.get("SITE_BASE", "https://juski1004.github.io/ai-trading/data/")
KST = dt.timezone(dt.timedelta(hours=9))


def today() -> str:
    return dt.datetime.now(KST).strftime("%Y-%m-%d")


def call(method: str, path: str, **params) -> dict:
    params["access_token"] = TOKEN
    url = path if path.startswith("http") else f"{API}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            # 토큰은 절대 출력하지 않음
            if e.code >= 500 and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise SystemExit(f"[인스타 API 오류 {e.code}] {body[:500]}")
    raise SystemExit("[인스타 API] 재시도 실패")


def fetch_json(rel: str) -> dict:
    with urllib.request.urlopen(SITE + rel + f"?v={int(time.time())}", timeout=30) as r:
        return json.loads(r.read())


def url(rel: str) -> str:
    return SITE + rel + f"?v={int(time.time())}"  # 인스타가 옛 파일(캐시)을 가져가지 않게


def wait_ready(cid: str, minutes: int = 8) -> None:
    end = time.time() + minutes * 60
    while time.time() < end:
        st = call("GET", cid, fields="status_code,status").get("status_code")
        if st == "FINISHED": return
        if st in ("ERROR", "EXPIRED"): raise SystemExit(f"[인스타] 미디어 처리 실패: {st}")
        time.sleep(6)
    raise SystemExit("[인스타] 미디어 처리 시간 초과")


def already_posted(caption: str) -> bool:
    first = caption.strip().splitlines()[0].strip()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=20)
    for m in call("GET", f"{uid()}/media", fields="caption,timestamp", limit=10).get("data", []):
        ts = dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        if ts >= since and (m.get("caption") or "").strip().splitlines()[:1] == [first]:
            return True
    return False


def publish(container: str) -> str:
    wait_ready(container)
    mid = call("POST", f"{uid()}/media_publish", creation_id=container)["id"]
    link = call("GET", mid, fields="permalink").get("permalink", "")
    print(f"게시 완료: {link}")
    return link


def post_carousel(images: list[str], caption: str) -> str:
    kids = [call("POST", f"{uid()}/media", image_url=url(p), is_carousel_item="true")["id"] for p in images]
    for k in kids: wait_ready(k, 3)
    c = call("POST", f"{uid()}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    return publish(c)


def post_reel(video: str, cover: str | None, caption: str) -> str:
    p = dict(media_type="REELS", video_url=url(video), caption=caption, share_to_feed="true")
    if cover: p["cover_url"] = url(cover)
    return publish(call("POST", f"{uid()}/media", **p)["id"])


def with_tags(caption: str, tags: str) -> str:
    tags = " ".join(t for t in tags.split() if t.startswith("#") and t not in caption)
    return f"{caption} {tags}".rstrip() if tags else caption


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["check", "cards", "cardsreel", "term", "reel"])
    ap.add_argument("--tags", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("IG_ACCESS_TOKEN"):
        raise SystemExit("IG_ACCESS_TOKEN 비밀값이 없습니다 (GitHub 저장소 Settings → Secrets 에 넣어 주세요)")

    if a.what == "check":
        me = call("GET", uid(), fields="username,followers_count,media_count")
        print(f"연결된 계정: @{me.get('username')} · 팔로워 {me.get('followers_count')} · 게시물 {me.get('media_count')}")
        if IGLOGIN:  # Instagram 로그인 토큰만 60일 만료 → 연장
            r = call("GET", "https://graph.instagram.com/refresh_access_token", grant_type="ig_refresh_token")
            print(f"토큰 연장 완료 · 남은 기간 약 {int(r.get('expires_in', 0)) // 86400}일")
        else:
            print("시스템 사용자 토큰 (만료 없음)")
        return

    if a.what in ("cards", "cardsreel"):
        j = fetch_json("cards/cards.json")
        if j["date"] != today() and not a.force:
            raise SystemExit(f"[건너뜀] 카드 날짜 {j['date']} 가 오늘({today()})이 아님 → 데이터 실행 먼저")
        cap = with_tags(j["caption"], a.tags)
        if not a.force and already_posted(cap): print("[건너뜀] 오늘 이미 올림"); return
        if a.what == "cards": post_carousel(j["images"], cap)
        else: post_reel("cards/reel.mp4", "cards/reel_cover.jpg", cap)
    elif a.what == "term":
        d = a.date or today()
        items = [i for i in fetch_json("termcards/termcards.json")["items"] if i["date"] == d]
        if not items: raise SystemExit(f"[건너뜀] {d} 용어 카드 없음")
        cap = with_tags(items[0]["caption"], a.tags)
        if not a.force and already_posted(cap): print("[건너뜀] 오늘 이미 올림"); return
        post_carousel(items[0]["images"], cap)
    elif a.what == "reel":
        j = fetch_json("reel/reel.json")
        if j["date"] != today() and not a.force:
            raise SystemExit(f"[건너뜀] 릴스 날짜 {j['date']} 가 오늘({today()})이 아님")
        cap = with_tags(j["caption"], a.tags)
        if not a.force and already_posted(cap): print("[건너뜀] 오늘 이미 올림"); return
        post_reel(j["video"], j.get("cover"), cap)


if __name__ == "__main__":
    main()
