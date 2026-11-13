/* 기관 매수 트래커 + 위치 진단 (2026-10-31 사용자: 참고 릴스에서 쓸 만한 것 가져오기)
   데이터: ../data/position.json (ai_trading/data/position.py 가 매일 장 마감 뒤 만듦)
   홈: 기관이 며칠째 사면서 거래량도 늘어난 종목 · 종목 화면: 기관·외국인 추정 평단 대비 지금 위치(반원 게이지)
   수급 담당(OSCAR 자리 직원)이 알려 줌 */
(() => {
  let PS = null;
  fetch("../data/position.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => {
    PS = j; const h = location.hash.slice(1).split("/")[0] || "home";
    if ((h === "home" || h === "analysis") && window.render) window.render();
  }).catch(() => {});
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(1) + "%";
  const eok = n => { const a = Math.abs(n), j = Math.floor(a / 1e4), r = a % 1e4; return (n < 0 ? "-" : "") + (j ? `${j}조${r ? ` ${r.toLocaleString("ko-KR")}억` : ""}` : `${a.toLocaleString("ko-KR")}억`); };
  const host = () => (window.Team ? { id: Team.photo("OSCAR"), name: Team.name("OSCAR") } : { id: "puppy", name: "서은찬" });

  function homeCard() {
    if (!PS || !PS.tracker || !PS.tracker.length) return "";
    const h = host(), top = PS.tracker.slice(0, 5);
    return `<section class="card ps-card"><div class="hd"><div><h2>기관 매수 트래커</h2><p class="sub">${esc(PS.date.slice(5).replace("-", "."))} 장 마감 · 기관이 며칠째 사면서 거래량도 늘어난 종목</p></div></div>
      <div class="dk-who"><img src="../img/team/${h.id}.jpg?v=4" alt=""><span><b>${esc(h.name)}</b><small>기관이 3일 넘게 연속으로 사고, 최근 거래량이 평소보다 30% 넘게 늘어난 종목이에요.</small></span></div>
      <ul class="list">${top.map((it, k) => `<li><button class="row" type="button" data-sym="${esc(it.sym)}">
        <span class="rank num">${k + 1}</span><span style="min-width:0"><div class="nm">${esc(it.name)}</div><div class="meta">기관 ${it.streak}일 연속 · ${eok(it.amt)} · 거래량 ${it.vol_ratio.toFixed(1)}배</div></span>
        <span class="rt"><div class="px num">${won(it.price)}</div><div class="meta num ${it.chg >= 0 ? "up" : "down"}">${(it.chg > 0 ? "+" : "") + it.chg.toFixed(2)}%</div></span></button></li>`).join("")}</ul>
      <p class="sub" style="margin-top:8px">공개 수급 자료로 계산한 참고 목록이에요. 투자 권유가 아니며, 기관이 산다고 꼭 오르지는 않아요.</p></section>`;
  }

  // 반원 게이지: 왼쪽 끝 -20%, 가운데 평단(0%), 오른쪽 끝 +20%
  function gauge(gap) {
    const g = Math.max(-20, Math.min(20, gap)), ang = Math.PI * (1 - (g + 20) / 40);
    const cx = 110, cy = 100, r = 80, x = cx + r * Math.cos(ang), y = cy - r * Math.sin(ang);
    return `<svg viewBox="0 0 220 120" class="ps-gauge" role="img" aria-label="평단 대비 ${pct(gap)}">
      <path d="M30 100 A80 80 0 0 1 190 100" fill="none" stroke="var(--line)" stroke-width="14" stroke-linecap="round"/>
      <path d="M30 100 A80 80 0 0 1 96 22" fill="none" stroke="var(--down)" stroke-width="14" stroke-linecap="round" opacity=".55"/>
      <path d="M124 22 A80 80 0 0 1 190 100" fill="none" stroke="var(--up)" stroke-width="14" stroke-linecap="round" opacity=".55"/>
      <line x1="110" y1="14" x2="110" y2="30" stroke="var(--fg)" stroke-width="2"/>
      <line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="var(--fg)" stroke-width="4" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="7" fill="var(--fg)"/>
      <text x="30" y="118" font-size="10" text-anchor="middle" fill="var(--dim)">-20%</text><text x="110" y="10" font-size="10" text-anchor="middle" fill="var(--dim)">평단</text><text x="190" y="118" font-size="10" text-anchor="middle" fill="var(--dim)">+20%</text></svg>`;
  }

  function detail(sym) {
    const it = PS && PS.items && PS.items[sym];
    if (!it || it.gap == null) return "";
    const tr = PS.tracker && PS.tracker.find(x => x.sym === sym);
    return `<section class="card ps-card"><div class="hd"><div><h2>위치 진단</h2><p class="sub">${esc(it.basis)} 추정 평균 단가 대비 지금 주가</p></div></div>
      <div class="ps-wrap">${gauge(it.gap)}<div class="ps-num"><b class="num ${it.gap >= 0 ? "up" : "down"}">${pct(it.gap)}</b><small>추정 평단 ${won(it.avg)}원 · 현재 ${won(it.price)}원</small></div></div>
      <p class="ps-say">${esc(it.verdict)}</p>
      ${it.org_streak ? `<p class="sub">기관 ${it.org_streak}일 연속 순매수${tr ? ` · 기관 매수 트래커 포착 (거래량 ${tr.vol_ratio.toFixed(1)}배)` : ""}</p>` : ""}
      <p class="sub" style="margin-top:8px">${esc(it.from.slice(5).replace("-", "."))}부터 ${it.days}거래일 순매수를 그날 종가로 쌓아 계산한 추정치예요. 실제 매매 가격과 그 전 보유분은 알 수 없어요. 투자 권유가 아니에요.</p></section>`;
  }

  const css = document.createElement("style");
  css.textContent = `.ps-wrap{display:flex;align-items:center;gap:12px;margin-top:6px}.ps-gauge{width:180px;flex:none}
  .ps-num{display:grid;gap:2px}.ps-num b{font-size:28px}.ps-num small{color:var(--dim);font-size:12px}
  .ps-say{margin:8px 0 4px;font-size:14.5px;line-height:1.5}`;
  document.head.appendChild(css);
  window.Position = { homeCard, detail };
})();
