/* 고성장 기업 발굴 (2026-10-29 사용자 요청 "종목 발굴 하나 넣자")
   데이터: ../data/growth.json (ai_trading/data/growth.py 가 매일 만듦) — 증권사 전망·분기 실적·목표가로 6가지 확인
   홈: 상위 5종목 카드 · 종목 화면: 6가지 체크 · 민채원(진입 계획 담당)이 안내 */
(() => {
  let GR = null;
  fetch("../data/growth.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => {
    GR = j; const h = location.hash.slice(1).split("/")[0] || "home";
    if ((h === "home" || h === "analysis") && window.render) window.render();
  }).catch(() => {});
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + Number(x).toFixed(2) + "%";
  const NAMES = { rev_est: "매출 성장 전망", eps_est: "이익 성장 전망", rev_yoy: "실제 매출 성장", margin: "이익률 개선", analyst: "증권사 시각", peg: "성장 대비 가격" };
  const ORDER = ["rev_est", "eps_est", "rev_yoy", "margin", "analyst", "peg"];
  const host = () => (window.Team ? { id: Team.photo("MILES"), name: Team.name("MILES") } : { id: "miles", name: "민채원" });
  const first = it => (it.checks.rev_est ? it.checks.rev_est.text.replace("예상 매출 ", "매출 ") : "");

  function homeCard() {
    if (!GR || !GR.items || !GR.items.length) return "";
    const h = host(), top = GR.items.slice(0, 5);
    return `<section class="card gr-card"><div class="hd"><div><h2>고성장 기업 발굴</h2><p class="sub">${esc(GR.date.slice(5).replace("-", "."))} 기준 · 6가지 성장 조건 중 많이 맞은 순</p></div></div>
      <div class="dk-who"><img src="../img/team/${h.id}.jpg?v=4" alt=""><span><b>${esc(h.name)}</b><small>매출·이익이 빠르게 늘고, 이익률이 좋아지고, 성장에 비해 가격이 비싸지 않은 회사를 골라 봤어요.</small></span></div>
      <ul class="list">${top.map((it, k) => `<li><button class="row" type="button" data-sym="${esc(it.sym)}">
        <span class="rank num">${k + 1}</span><span style="min-width:0"><div class="nm">${esc(it.name)}</div><div class="meta">${it.score}/${it.n} · ${esc(first(it))}</div></span>
        <span class="rt"><div class="px num">${won(it.price)}</div><div class="meta num ${it.chg >= 0 ? "up" : "down"}">${pct(it.chg)}</div></span></button></li>`).join("")}</ul>
      <p class="sub" style="margin-top:8px">증권사 전망과 공시 실적을 숫자 조건으로 걸러 낸 참고 목록이에요. 전망은 틀릴 수 있고, 투자 권유가 아니에요.</p></section>`;
  }

  function detail(sym) {
    const it = GR && GR.items && GR.items.find(x => x.sym === sym);
    if (!it) return "";
    return `<section class="card gr-card"><div class="hd"><div><h2>고성장 기업 조건 ${it.score}/${it.n}</h2><p class="sub">증권사 전망·분기 실적·목표가 기준</p></div></div>
      <ul class="rb-checks">${ORDER.filter(k => it.checks[k]).map(k => { const c = it.checks[k]; return `<li class="${c.ok ? "ok" : "no"}"><b>${c.ok ? "✓" : "–"} ${NAMES[k]}</b><span>${esc(c.text)}</span></li>`; }).join("")}</ul>
      <p class="sub" style="margin-top:8px">숫자 조건을 기계적으로 확인한 참고 정보예요. 투자 권유가 아니에요.</p></section>`;
  }
  window.Growth = { homeCard, detail, data: () => GR };
})();
