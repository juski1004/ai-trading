"""장마감 요약 아카이브 — 매일 한 편씩 쌓이는 글 페이지 (애드센스·검색용 콘텐츠).

- web/archive/YYYY-MM-DD.html : 그날 장마감 요약 글 (지수·상승/하락 종목과 이유·수급·내일 체크 포인트·진행 직원)
- web/archive/img/YYYY-MM-DD.jpg : 그날 카드뉴스 표지 (가볍게 JPG)
- web/archive/index.html, index.json : 전체 목록 (최근이 위)
- 사이트(site 브랜치)는 매번 새로 덮어쓰므로, 워크플로가 먼저 지난 archive/ 를 site 에서 꺼내 온 뒤 이걸 돌린다.
- 숫자는 데이터(scores·outlook facts)에서 그대로. AI가 쓴 시황 문장은 숫자를 틀릴 수 있어 쓰지 않는다.
  '알파의 선택'은 18:10 공개라 넣지 않는다. 매매를 권하는 문장은 쓰지 않는다.
실행: python -m ai_trading.data.archive web
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from .cards import host_of

SITE = "https://juski1004.github.io/ai-trading"
CSS = """:root{--ink:#1d2033;--muted:#6b7088;--lav:#6c5ce7;--line:#e6e4f5;--up:#e2486b;--down:#3d6fe6}
*{box-sizing:border-box}body{margin:0;background:#f6f7fb;color:var(--ink);font-family:"Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.75;font-size:16px}
main{max-width:720px;margin:0 auto;padding:20px 16px 60px}a{color:var(--lav)}
header.top{display:flex;justify-content:space-between;align-items:center;font-weight:800;color:var(--lav);margin-bottom:10px}
h1{font-size:24px;line-height:1.35;margin:6px 0 4px}h2{font-size:18px;margin:28px 0 8px}.sub{color:var(--muted);font-size:14px}
.cover{width:100%;max-width:420px;border-radius:18px;display:block;margin:14px 0;box-shadow:0 10px 30px rgba(40,50,90,.12)}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;font-size:15px}td,th{padding:9px 10px;white-space:nowrap;border-bottom:1px solid var(--line);text-align:left}th{color:var(--muted);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}.up{color:var(--up)}.down{color:var(--down)}
ul.mv{list-style:none;padding:0;margin:0}ul.mv li{background:#fff;border:1px solid var(--line);border-radius:14px;padding:10px 14px;margin-bottom:8px}
ul.mv b{font-size:16px}.tag{display:inline-block;font-size:12px;font-weight:700;border-radius:8px;padding:1px 7px;margin-right:6px;background:#f0f1f6;color:var(--muted)}
.tag.호재{background:#ffe9ee;color:var(--up)}.tag.악재{background:#e8f0ff;color:var(--down)}
.note{margin-top:30px;font-size:13px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
ol.list{padding-left:20px}ol.list li{margin-bottom:6px}.nav{display:flex;justify-content:space-between;gap:10px;margin-top:24px;font-size:14px}"""


def _pct(x):
    return f"{'+' if x > 0 else ''}{x:.2f}%"


def _cls(x):
    return "up" if x > 0 else "down" if x < 0 else ""


def _eok(x):
    return f"{'+' if x > 0 else ''}{x:,.0f}억 원"


def _page(title, desc, body, canon, image=None):
    e = html.escape
    og = f'<meta property="og:image" content="{e(image)}">' if image else ""
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{e(canon)}">
<meta property="og:type" content="article"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">{og}
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>{CSS}</style></head><body><main>
<header class="top"><a href="index.html" style="text-decoration:none">AI 투자연구소 · 장마감 요약</a><span class="sub">평일 매일</span></header>
{body}
<p class="note">이 글은 공개된 시세·수급 데이터와 그날 뉴스 제목을 정리한 참고 자료이며 투자 권유가 아닙니다. 시세는 거래소 종가 기준이고, 투자 판단과 결과의 책임은 본인에게 있습니다.</p>
</main></body></html>"""


def build(web: Path) -> dict | None:
    web = Path(web); data = web / "data"; arc = web / "archive"; (arc / "img").mkdir(parents=True, exist_ok=True)
    sc = json.loads((data / "scores.json").read_text(encoding="utf-8"))
    o = json.loads((data / "outlook.json").read_text(encoding="utf-8"))
    whyp = data / "why.json"; why = json.loads(whyp.read_text(encoding="utf-8")) if whyp.exists() else {}
    date = sc["date"]; fx = o.get("facts") or {}; S = sc["stocks"]; m = sc["market"]
    md = f"{int(date[5:7])}월 {int(date[8:])}일"
    k, q = m["kospi"], m["kosdaq"]
    hid, hname, hrole = host_of(date)
    W = why.get("sym", {}) if why.get("date") == date else {}
    ranked = sorted(S.items(), key=lambda x: -x[1]["chg"])
    up = sum(1 for s in S.values() if s["chg"] > 0); dn = sum(1 for s in S.values() if s["chg"] < 0)
    e = html.escape

    def mover(sym, s):
        w = W.get(sym) or {}; line = w.get("line") or ""; tag = w.get("tone", "중립")
        if (not line or "뚜렷한" in line) and w.get("title"):
            line, tag = f"관련 기사: {w['title']} ({w.get('src', '')})", "뉴스"
        line = line or "뚜렷한 개별 소식은 없었어요."
        return f'<li><b>{e(s["name"])}</b> <span class="{_cls(s["chg"])}">{_pct(s["chg"])}</span> · {s["price"]:,.0f}원<br><span class="tag {e(tag)}">{e(tag)}</span>{e(line)}</li>'

    # 표지 이미지
    img_rel = None
    cover = data / "cards" / "1.png"
    if cover.exists():
        try:
            from PIL import Image
            Image.open(cover).convert("RGB").resize((720, 900)).save(arc / "img" / f"{date}.jpg", quality=80, optimize=True)
            img_rel = f"img/{date}.jpg"
        except Exception as ex:  # 그림이 없어도 글은 만든다
            print(f"[아카이브 표지 실패] {ex}")

    rows = []
    for lab, key in (("코스피", "코스피"), ("코스닥", "코스닥")):
        v = fx.get(key) or {}; now = k if key == "코스피" else q
        rows.append(f'<tr><td>{lab}</td><td class="n">{now["v"]:,.2f}</td><td class="n {_cls(now["chg"])}">{_pct(now["chg"])}</td>'
                    f'<td class="n {_cls(v.get("5일", 0))}">{_pct(v["5일"]) if "5일" in v else "-"}</td><td class="n {_cls(v.get("20일", 0))}">{_pct(v["20일"]) if "20일" in v else "-"}</td></tr>')
    mf = fx.get("오늘_시장수급_억원") or {}
    flow = "".join(f'<tr><td>{lab}</td>' + "".join(f'<td class="n {_cls(mf[key][w])}">{_eok(mf[key][w])}</td>' for w in ("frg", "org", "ind")) + "</tr>"
                   for lab, key in (("코스피", "KOSPI"), ("코스닥", "KOSDAQ")) if key in mf)
    pts = []
    if "KOSPI" in mf:
        f0 = mf["KOSPI"]["frg"]; pts.append(f"외국인 흐름 — 오늘 코스피에서 {_eok(f0)} {'순매수' if f0 > 0 else '순매도'}")
    if fx.get("WTI_20일%") is not None: pts.append(f"국제유가 — 최근 한 달 {_pct(fx['WTI_20일%'])}")
    if fx.get("미국10년물") is not None: pts.append(f"미국 10년 금리 {fx['미국10년물']}% · 공포지수 VIX {fx.get('VIX')}")
    ma = fx.get("대형주_20일선_위_비율")
    if ma: pts.append(f"20일 이동평균선 위에 있는 대형주 {ma['20일선_위']}/{ma['전체']}종목")

    title = f"{md} 장마감 요약 — 코스피 {_pct(k['chg'])}, 코스닥 {_pct(q['chg'])}"
    desc = (f"{date} 코스피 {k['v']:,.2f}({_pct(k['chg'])}), 코스닥 {q['v']:,.2f}({_pct(q['chg'])}). "
            f"많이 오른 {ranked[0][1]['name']} {_pct(ranked[0][1]['chg'])}, 많이 내린 {ranked[-1][1]['name']} {_pct(ranked[-1][1]['chg'])}. 수급과 내일 체크 포인트.")
    body = f"""<h1>{e(title)}</h1>
<p class="sub">{e(date)} 장 마감 기준 · 진행 {e(hname)} ({e(hrole)})</p>
{f'<img class="cover" src="{img_rel}" alt="{e(md)} 장마감 요약 카드" loading="lazy">' if img_rel else ""}
<p>오늘 코스피는 <b>{k['v']:,.2f}</b>로 <b class="{_cls(k['chg'])}">{_pct(k['chg'])}</b>, 코스닥은 <b>{q['v']:,.2f}</b>로 <b class="{_cls(q['chg'])}">{_pct(q['chg'])}</b> 마감했어요.
대형주 {len(S)}종목 중 <b class="up">{up}개가 오르고</b> <b class="down">{dn}개가 내렸어요</b>.{f" 원/달러 환율은 {m['usdkrw']['v']:,.0f}원이에요." if m.get('usdkrw') else ""}</p>
<h2>지수 흐름</h2>
<table><tr><th></th><th>종가</th><th>하루</th><th>1주</th><th>1달</th></tr>{''.join(rows)}</table>
<h2>많이 오른 종목</h2><ul class="mv">{''.join(mover(s, x) for s, x in ranked[:5])}</ul>
<h2>많이 내린 종목</h2><ul class="mv">{''.join(mover(s, x) for s, x in ranked[-5:][::-1])}</ul>
{f'<h2>누가 사고 팔았나 (순매수)</h2><table><tr><th></th><th>외국인</th><th>기관</th><th>개인</th></tr>{flow}</table>' if flow else ""}
{f'<h2>내일 체크 포인트</h2><ol class="list">{"".join(f"<li>{e(p)}</li>" for p in pts)}</ol>' if pts else ""}"""

    idxp = arc / "index.json"
    items = json.loads(idxp.read_text(encoding="utf-8")) if idxp.exists() else []
    items = [x for x in items if x.get("date") != date]
    items.append({"date": date, "title": title, "desc": desc, "img": img_rel})
    items.sort(key=lambda x: x["date"], reverse=True)
    i = [x["date"] for x in items].index(date)
    older = items[i + 1] if i + 1 < len(items) else None
    nav = f"""<div class="nav"><span>{f'<a href="{older["date"]}.html">‹ {e(older["date"])}</a>' if older else ""}</span><a href="index.html">전체 목록 ›</a></div>"""  # 다음 날 글은 그날 생기므로 '이전 글'과 목록만
    (arc / f"{date}.html").write_text(_page(title, desc, body + nav, f"{SITE}/archive/{date}.html", f"{SITE}/archive/{img_rel}" if img_rel else None), encoding="utf-8")

    lis = "".join(f'<li><a href="{x["date"]}.html"><b>{e(x["title"])}</b></a><br><span class="sub">{e(x["desc"])}</span></li>' for x in items)
    (arc / "index.html").write_text(_page("장마감 요약 모음 — AI 투자연구소", "평일 매일 코스피·코스닥 장마감 요약: 지수, 많이 오른·내린 종목과 이유, 수급, 내일 체크 포인트.",
                                          f'<h1>장마감 요약 모음</h1><p class="sub">평일 매일 장 마감 뒤 올라와요 · {len(items)}편</p><ul class="mv">{lis}</ul>',
                                          f"{SITE}/archive/"), encoding="utf-8")
    idxp.write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")
    # 검색 엔진용 사이트맵
    urls = [f"{SITE}/archive/"] + [f"{SITE}/archive/{x['date']}.html" for x in items]
    (arc / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>\n", encoding="utf-8")
    return {"date": date, "count": len(items)}


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "web")))
