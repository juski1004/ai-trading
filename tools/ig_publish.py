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
IG_API = "https://graph.instagram.com/v23.0"
FB_API = "https://graph.facebook.com/v23.0"
IGLOGIN = TOKEN.startswith("IG")
API = IG_API if IGLOGIN else FB_API
_UID: list[str] = []


def pick_api() -> None:
    """토큰 종류를 앞글자로만 판단하면 틀릴 수 있어(인스타 로그인으로 만든 EAA 토큰 등),
    인스타 주소에서 먼저 확인해 보고 되면 그쪽을 쓴다. 안 되면 페이스북 주소 그대로."""
    global IGLOGIN, API
    q = urllib.parse.urlencode({"fields": "user_id,username", "access_token": TOKEN})
    try:
        with urllib.request.urlopen(f"{IG_API}/me?{q}", timeout=30) as r:
            if json.loads(r.read()).get("username"):
                IGLOGIN, API = True, IG_API
                return
    except (urllib.error.URLError, ValueError):
        pass
    IGLOGIN, API = False, FB_API


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


ROOT = SITE.rsplit("data/", 1)[0]  # 사이트 맨 위 (미리 만든 content/ 가 여기 있음)


def fetch_json(rel: str, base: str = "") -> dict:
    with urllib.request.urlopen((base or SITE) + rel + f"?v={int(time.time())}", timeout=30) as r:
        return json.loads(r.read())


def try_json(rel: str, base: str = "") -> dict:
    """없을 수도 있는 파일 (그날 새로 만든 릴스·용어 카드): 없으면 빈 값."""
    try:
        return fetch_json(rel, base)
    except (urllib.error.URLError, ValueError):
        return {}


def url(rel: str) -> str:
    """rel: data/ 기준 경로, 또는 http 로 시작하는 전체 주소.
    인스타 API는 JPEG만 받으므로 .png 는 데이터 실행이 같이 만든 .jpg 사본을 쓴다."""
    if rel.endswith(".png"): rel = rel[:-4] + ".jpg"
    base = "" if rel.startswith("http") else SITE
    return base + rel + f"?v={int(time.time())}"  # 인스타가 옛 파일(캐시)을 가져가지 않게


def wait_ready(cid: str, minutes: int = 8) -> None:
    end = time.time() + minutes * 60
    while time.time() < end:
        st = call("GET", cid, fields="status_code,status").get("status_code")
        if st == "FINISHED": return
        if st in ("ERROR", "EXPIRED"): raise SystemExit(f"[인스타] 미디어 처리 실패: {st}")
        time.sleep(6)
    raise SystemExit("[인스타] 미디어 처리 시간 초과")


def already_posted(caption: str, reel: bool = False) -> bool:
    """20시간 안에 같은 첫 줄 + 같은 종류(릴스/피드)로 올린 게 있으면 True.
    카드(캐러셀)와 카드 릴스는 캡션이 같아도 서로 다른 게시물이라 종류까지 본다."""
    first = caption.strip().splitlines()[0].strip()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=20)
    for m in call("GET", f"{uid()}/media", fields="caption,timestamp,media_product_type", limit=10).get("data", []):
        ts = dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        is_reel = m.get("media_product_type") == "REELS"
        if ts >= since and is_reel == reel and (m.get("caption") or "").strip().splitlines()[:1] == [first]:
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


def gh(method: str, path: str, body: dict | None = None) -> dict:
    """GitHub API (Actions 안에서만: GH_TOKEN·GITHUB_REPOSITORY)."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/{path}",
        data=json.dumps(body).encode() if body is not None else None, method=method,
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read()
        return json.loads(t) if t else {}


def ensure_today_cards(j: dict, wait_min: int = 45) -> dict:
    """오늘 카드가 아직 없을 때 (미라 예약 작업이 하던 일):
    오늘 15:30 이후 데이터 실행이 없으면 trade.yml(data)을 직접 실행시키고, 카드가 나올 때까지 기다린다."""
    if not (os.environ.get("GH_TOKEN") and os.environ.get("GITHUB_REPOSITORY")):
        return j
    now = dt.datetime.now(KST)
    if now.weekday() >= 5 or now.hour < 16:  # 주말이거나 장마감 데이터 시간 전이면 그대로
        return j
    since = now.replace(hour=15, minute=30, second=0, microsecond=0).astimezone(dt.timezone.utc)
    runs = gh("GET", "actions/workflows/trade.yml/runs?per_page=10").get("workflow_runs", [])
    recent = [r for r in runs if dt.datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) >= since]
    if not recent:
        print("[데이터] 오늘 장마감 데이터 실행이 없어 직접 실행시킴")
        gh("POST", "actions/workflows/trade.yml/dispatches", {"ref": "main", "inputs": {"command": "data"}})
    else:
        print(f"[데이터] 오늘 데이터 실행 {len(recent)}건 있음 (상태: {', '.join(r['status'] for r in recent)}) → 카드 기다림")
    end = time.time() + wait_min * 60
    while time.time() < end:
        time.sleep(120)
        j = fetch_json("cards/cards.json")
        if j["date"] == today():
            print("[데이터] 오늘 카드 준비됨")
            time.sleep(60)  # JPG 사본까지 사이트에 다 올라가게 잠깐 더
            return j
    return j


def skip(msg: str) -> None:
    """올릴 게 없을 때(휴장일·이미 올림 등): 실패가 아니므로 정상 종료 → 실패 알림 이슈가 안 생김."""
    print(msg)
    sys.exit(0)


def mover_tags() -> str:
    """그날 가장 많이 오른·내린 종목 이름 해시태그 2개 (미라 예약 작업이 하던 것)."""
    try:
        st = [s for s in fetch_json("scores.json").get("stocks", {}).values() if s.get("chg") is not None]
        st.sort(key=lambda s: s["chg"])
        return " ".join("#" + s["name"].replace(" ", "") for s in (st[-1], st[0])) if st else ""
    except Exception:  # 태그가 없어도 게시는 계속
        return ""


def with_tags(caption: str, tags: str) -> str:
    tags = " ".join(t for t in tags.split() if t.startswith("#") and t not in caption)
    return f"{caption} {tags}".rstrip() if tags else caption


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["check", "cards", "cardsreel", "term", "reel", "stats"])
    ap.add_argument("--tags", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("IG_ACCESS_TOKEN"):
        raise SystemExit("IG_ACCESS_TOKEN 비밀값이 없습니다 (GitHub 저장소 Settings → Secrets 에 넣어 주세요)")
    pick_api()
    print("연결 방식:", "Instagram 로그인 (graph.instagram.com)" if IGLOGIN else "Facebook 통합 로그인 (graph.facebook.com)")

    if a.what == "check":
        me = call("GET", uid(), fields="username,followers_count,media_count")
        print(f"연결된 계정: @{me.get('username')} · 팔로워 {me.get('followers_count')} · 게시물 {me.get('media_count')}")
        if IGLOGIN:  # Instagram 로그인 토큰: 60일 만료 → 여기서 연장
            r = call("GET", "https://graph.instagram.com/refresh_access_token", grant_type="ig_refresh_token")
            print(f"토큰 연장 완료 · 남은 기간 약 {int(r.get('expires_in', 0)) // 86400}일")
            return
        # 페이스북 사용자 토큰(그래프 API 탐색기 → 장기 토큰): 60일 만료, 자동 연장 불가 → 14일 전부터 실패로 알림
        exp = int(call("GET", "debug_token", input_token=TOKEN).get("data", {}).get("expires_at") or 0)
        if not exp:
            print("토큰 만료 없음")
            return
        left = (exp - time.time()) / 86400
        print(f"토큰 만료: {dt.datetime.fromtimestamp(exp, KST):%Y-%m-%d} (남은 {left:.0f}일)")
        if left < 14:
            raise SystemExit(f"[토큰 곧 만료] {left:.0f}일 남음 → 그래프 API 탐색기에서 토큰을 새로 만들어 "
                             "장기 토큰으로 연장한 뒤 GitHub 비밀값 IG_ACCESS_TOKEN 을 바꿔 주세요")
        return

    if a.what == "stats":
        # 최근 게시물 성과 (읽기만). 조회·도달은 insights 권한이 있을 때만 나옴
        me = call("GET", uid(), fields="username,followers_count,media_count")
        print(f"@{me.get('username')} · 팔로워 {me.get('followers_count')} · 게시물 {me.get('media_count')}")
        since = dt.datetime.now(KST) - dt.timedelta(days=int(a.date or 14))
        items = call("GET", f"{uid()}/media", limit=50,
                     fields="id,timestamp,media_type,media_product_type,like_count,comments_count,caption,permalink").get("data", [])
        print("날짜(KST)|종류|좋아요|댓글|조회|도달|저장|공유|캡션")
        for m in items:
            t = dt.datetime.strptime(m["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).astimezone(KST)
            if t < since: break
            ins = {}
            try:
                q = urllib.parse.urlencode({"metric": "views,reach,saved,shares", "access_token": TOKEN})
                with urllib.request.urlopen(f"{API}/{m['id']}/insights?{q}", timeout=30) as r:
                    ins = {d["name"]: d["values"][0]["value"] for d in json.loads(r.read()).get("data", [])}
            except (urllib.error.URLError, ValueError, KeyError, IndexError):
                pass
            cap = (m.get("caption") or "").replace("\n", " ")[:28]
            print(f"{t:%m-%d %H:%M}|{m.get('media_product_type') or m.get('media_type')}|{m.get('like_count')}|"
                  f"{m.get('comments_count')}|{ins.get('views','-')}|{ins.get('reach','-')}|{ins.get('saved','-')}|"
                  f"{ins.get('shares','-')}|{cap}")
        return

    if a.what in ("cards", "cardsreel"):
        j = fetch_json("cards/cards.json")
        if j["date"] != today() and not a.force:
            j = ensure_today_cards(j)
        if j["date"] != today() and not a.force:
            skip(f"[건너뜀] 카드 날짜 {j['date']} 가 오늘({today()})이 아님 → 데이터 실행 먼저")
        cap = with_tags(j["caption"], a.tags or mover_tags())
        if not a.force and already_posted(cap, reel=a.what == "cardsreel"): print("[건너뜀] 오늘 이미 올림"); return
        if a.what == "cards": post_carousel(j["images"], cap)
        else: post_reel("cards/reel.mp4", "cards/reel_cover.jpg", cap)
    elif a.what == "term":
        # 그날 데이터 실행이 새로 만든 것(data/termcards) → 없으면 미리 만든 것(content/termcards)
        d = a.date or today()
        item = next((i for i in try_json("termcards/termcards.json").get("items", []) if i["date"] == d), None)
        if not item:
            item = next((i for i in try_json("content/termcards/termcards.json", ROOT).get("items", []) if i["date"] == d), None)
            if item: item = {**item, "images": [ROOT + p for p in item["images"]]}
        if not item: skip(f"[건너뜀] {d} 용어 카드 없음")
        cap = with_tags(item["caption"], a.tags)
        if not a.force and already_posted(cap): print("[건너뜀] 오늘 이미 올림"); return
        post_carousel(item["images"], cap)
    elif a.what == "reel":
        # 금요일 앱 광고 릴스: 그날 새로 만든 것(data/reel) → 없으면 미리 만든 것(content/reels)
        d = a.date or today()
        j = try_json("reel/reel.json")
        if j.get("date") != d:
            pre = next((i for i in try_json("content/reels/reels.json", ROOT).get("items", []) if i["date"] == d), None)
            if pre: j = {**pre, "video": ROOT + pre["video"], "cover": ROOT + pre["cover"] if pre.get("cover") else None}
        if j.get("date") != d and not (a.force and j.get("video")):
            skip(f"[건너뜀] {d} 릴스 없음 (새로 만든 것 {j.get('date')})")
        cap = with_tags(j["caption"], a.tags)
        if not a.force and already_posted(cap, reel=True): print("[건너뜀] 오늘 이미 올림"); return
        post_reel(j["video"], j.get("cover"), cap)


if __name__ == "__main__":
    main()
