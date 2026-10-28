/* 바닥 반등 신호 (2026-10-29 사용자 요청: 하락 후 아래꼬리·거래량·바닥 골든크로스·기관 외국인 매집을 잡아서 보여 주기)
   데이터: ../data/rebound.json (ai_trading/data/rebound.py 가 매일 장 마감 뒤 만듦)
   홈: 신호가 많은 순 5종목 카드 · 종목 화면: 그 종목의 6개 신호 체크 · 차유나(차트 담당)가 알려 줌 */
(() => {
  let RB = null;
  fetch("../data/rebound.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => {
    RB = j; const h = location.hash.slice(1).split("/")[0] || "home";
    if ((h === "home" || h === "analysis") && window.render) window.render();
  }).catch(() => {});
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const NAMES = { drop: "크게 하락", tail: "아래꼬리", volume: "거래량 증가", macd: "바닥 골든크로스", flow: "기관·외국인 매수", rebound: "반등 시작" };
  const ORDER = ["drop", "tail", "volume", "macd", "flow", "rebound"];
  const dots = n => `<span class="rb-dots" aria-label="신호 ${n + 1}개">${"●".repeat(n + 1)}<i>${"●".repeat(5 - n)}</i></span>`;
  const host = () => (window.Team ? { id: Team.photo("RAY"), name: Team.name("RAY") } : { id: "ray", name: "차유나" });

  function homeCard() {
    if (!RB || !RB.items || !RB.items.length) return "";
    const h = host(), top = RB.items.slice(0, 5);
    return `<section class="card rb-card"><div class="hd"><div><h2>바닥 반등 신호</h2><p class="sub">${esc(RB.date.slice(5).replace("-", "."))} 장 마감 · 6개 신호 중 많이 맞은 순</p></div></div>
      <div class="dk-who"><img src="../img/team/${h.id}.jpg?v=4" alt=""><span><b>${esc(h.name)}</b><small>크게 떨어진 뒤 아래꼬리·거래량·바닥 골든크로스·기관 외국인 매수가 함께 나온 종목을 골라 봤어요.</small></span></div>
      <ul class="list rb-list">${top.map((it, k) => `<li><button class="row" type="button" data-sym="${esc(it.sym)}">
        <span class="rank num">${k + 1}</span><span style="min-width:0"><div class="nm">${esc(it.name)}</div><div class="meta">${dots(it.score)} 저점 대비 ${pct((it.price / it.low - 1) * 100)}</div></span>
        <span class="rt"><div class="px num">${won(it.price)}</div><div class="meta num ${it.chg >= 0 ? "up" : "down"}">${pct(it.chg)}</div></span></button></li>`).join("")}</ul>
      <p class="sub" style="margin-top:8px">차트와 수급 조건을 기계적으로 걸러 낸 참고 목록이에요. 투자 권유가 아니며, 떨어지던 흐름이 다시 이어질 수도 있어요.</p></section>`;
  }

  function detail(sym) {
    const it = RB && RB.items && RB.items.find(x => x.sym === sym);
    if (!it) return "";
    return `<section class="card rb-card"><div class="hd"><div><h2>바닥 반등 신호 ${it.score + 1}/6</h2><p class="sub">${esc(it.low_date.slice(5).replace("-", "."))} 저점 ${won(it.low)}원 이후</p></div></div>
      <ul class="rb-checks">${ORDER.map(k => { const c = it.checks[k]; return `<li class="${c.ok ? "ok" : "no"}"><b>${c.ok ? "✓" : "–"} ${NAMES[k]}</b><span>${esc(c.text)}</span></li>`; }).join("")}</ul>
      <p class="sub" style="margin-top:8px">조건을 기계적으로 확인한 참고 정보예요. 투자 권유가 아니에요.</p></section>`;
  }

  const css = document.createElement("style");
  css.textContent = `.rb-dots{color:var(--up);letter-spacing:1px;font-size:11px;margin-right:4px}.rb-dots i{color:var(--line);font-style:normal}
  .rb-checks{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:8px}
  .rb-checks li{display:grid;gap:2px;padding:9px 11px;border-radius:12px;background:var(--soft)}
  .rb-checks li b{font-size:13.5px}.rb-checks li.ok b{color:var(--pos)}.rb-checks li.no{opacity:.6}
  .rb-checks li span{font-size:12.5px;color:var(--muted)}`;
  document.head.appendChild(css);
  window.Rebound = { homeCard, detail, data: () => RB };
})();
