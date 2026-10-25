/* 주식 용어 사전 (#learn, #learn/per): 초보자용 지표 설명 + 오늘 실제 값.
   - 설명은 glossary.json (릴스 제작 ai_trading/reel.py 와 같은 파일)
   - 홈에는 '오늘의 용어' 카드 하나 (날짜마다 바뀜)
   - 예시 종목은 삼성전자 (대형주 대표). 숫자는 그날 데이터 그대로, 권유 문장 없음 */
(() => {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let G = null, O = null;
  const ready = Promise.all([
    fetch("glossary.json", { cache: "no-cache" }).then(r => r.json()).then(j => (G = j)).catch(() => null),
    fetch("../data/outlook.json", { cache: "no-cache" }).then(r => r.json()).then(j => (O = j)).catch(() => null),
  ]).then(() => { if (/^#learn/.test(location.hash) || /^#?(home)?$/.test(location.hash)) window.dispatchEvent(new HashChangeEvent("hashchange")); });

  const EX = "005930.KS";
  const num = (v, d = 2) => Number(v).toLocaleString("ko-KR", { maximumFractionDigits: d });
  const sgn = v => (v > 0 ? "+" : "") + num(v);
  const UNIT = { per: "배", pbr: "배", roe: "%", div_yield: "%", debt: "%", margin: "%" };

  // 오늘 실제 값 한 줄 (없으면 빈 문자열)
  function live(t) {
    const SC = window.__SC; if (!t.live || !SC) return "";
    const s = SC.stocks && SC.stocks[EX], f = (O && O.facts) || {}, d = SC.date.slice(5).replace("-", ".");
    try {
      if (t.live.startsWith("fin.")) { const k = t.live.slice(4), v = s && s.fin && s.fin[k]; return v == null ? "" : `${s.name} ${t.name} ${num(v)}${UNIT[k] || ""} (${d})`; }
      if (t.live === "VIX" && f.VIX != null) return `${d} VIX ${f.VIX}`;
      if (t.live === "미국10년물" && f["미국10년물"] != null) return `${d} 미국 10년 금리 ${f["미국10년물"]}%`;
      if (t.live === "usdkrw" && SC.market.usdkrw) return `${d} 원/달러 ${num(SC.market.usdkrw.v, 1)}원`;
      if (t.live === "WTI_20일%" && f["WTI_20일%"] != null) return `WTI 최근 한 달 ${sgn(f["WTI_20일%"])}% (${d})`;
      if (t.live === "frg") { const m = f["오늘_시장수급_억원"]; if (m) return `${d} 외국인 코스피 ${sgn(m.KOSPI.frg)}억 · 기관 ${sgn(m.KOSPI.org)}억`; }
      if (t.live === "ma20" && s) { const m = (s.tech || []).find(x => x[0] === "20일 이동평균"); if (m) return `${s.name} 종가 ${num(s.price, 0)}원 · 20일선 ${num(m[1], 0)}원 (${s.price >= m[1] ? "위" : "아래"})`; }
    } catch (e) {}
    return "";
  }
  const today = () => { const T = G.terms, d = (window.__SC && window.__SC.date) || ""; let h = 0; for (const c of d) h = (h * 31 + c.charCodeAt(0)) >>> 0; return T[h % T.length]; };

  function card(t, open) {
    const v = live(t);
    return `<details class="lr-t" id="lr-${esc(t.id)}"${open ? " open" : ""}><summary><b>${esc(t.name)}</b><span>${esc(t.full)}</span></summary>
      <p class="lr-one">${esc(t.one)}</p><p>${esc(t.body)}</p><p class="lr-how"><b>읽는 법</b> ${esc(t.how)}</p>${v ? `<p class="lr-live">📌 ${esc(v)}</p>` : ""}</details>`;
  }
  function view(arg) {
    if (!G) return `<div class="card"><div class="skel" style="width:40%"></div><div class="skel"></div></div>`;
    const t0 = today();
    return `<a class="back" href="#home">‹ 홈</a>
    <section class="card lr-hero"><h2>📘 주식 용어 사전</h2><p class="sub">처음이라도 괜찮아요. 뉴스와 앱에 자주 나오는 말을 한 줄씩, 오늘 실제 숫자와 함께 풀어 드려요.</p></section>
    ${G.groups.map(g => `<section class="card"><div class="hd"><h2>${g.emoji} ${esc(g.name)}</h2></div>
      ${G.terms.filter(t => t.g === g.id).map(t => card(t, t.id === arg)).join("")}</section>`).join("")}
    <p class="note">공개 자료로 만든 학습용 설명이에요. 특정 종목을 사고팔라는 뜻이 아니에요. 오늘의 용어: ${esc(t0.name)}</p>`;
  }
  function homeCard() {
    if (!G) return "";
    const t = today(), v = live(t);
    return `<a class="card lr-home" href="#learn/${esc(t.id)}"><span class="lr-tag">오늘의 용어</span><b>${esc(t.q)}</b><p>${esc(t.one)}</p>${v ? `<small>📌 ${esc(v)}</small>` : ""}<em>용어 사전 ${G.terms.length}개 보기 ›</em></a>`;
  }
  function mount(arg) { // 특정 용어로 들어오면 그 자리로 스크롤
    if (!arg) return; const el = document.getElementById("lr-" + arg);
    if (el) setTimeout(() => el.scrollIntoView({ block: "start", behavior: "smooth" }), 60);
  }

  const css = document.createElement("style");
  css.textContent = `
  .lr-home{display:block;text-decoration:none;color:inherit}.lr-home b{display:block;font-size:17px;margin:6px 0 2px}.lr-home p{margin:0;font-size:14px;color:var(--muted,#6b7088)}
  .lr-home small{display:block;margin-top:6px;font-size:13px;color:var(--lav-d,#6c5ce7);font-weight:700}.lr-home em{display:block;margin-top:8px;font-style:normal;font-size:13px;font-weight:700;color:var(--lav-d,#6c5ce7)}
  .lr-tag{display:inline-block;font-size:12px;font-weight:700;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:10px;padding:2px 9px}
  .lr-t{border-top:1px solid var(--line,#eceaf7);padding:10px 0}.lr-t:first-of-type{border-top:0}
  .lr-t summary{display:flex;gap:8px;align-items:baseline;cursor:pointer;list-style:none}.lr-t summary::-webkit-details-marker{display:none}
  .lr-t summary b{font-size:16px}.lr-t summary span{font-size:13px;color:var(--muted,#6b7088);flex:1}.lr-t summary::after{content:"＋";color:var(--lav-d,#6c5ce7);font-weight:800}
  .lr-t[open] summary::after{content:"－"}.lr-t p{margin:8px 0 0;font-size:14.5px;line-height:1.65}.lr-one{font-weight:700}
  .lr-how{background:var(--soft,#f6f5fd);border-radius:12px;padding:8px 10px}.lr-how b{color:var(--lav-d,#6c5ce7);margin-right:4px}
  .lr-live{font-weight:700;color:var(--lav-d,#6c5ce7)}`;
  document.head.appendChild(css);
  window.Learn = { view, homeCard, mount, ready, terms: () => (G ? G.terms : []) };
})();
