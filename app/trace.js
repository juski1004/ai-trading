/* 큰손 매수 흔적 ◆ (2026-11-03 사용자: 참고 영상처럼 차트에 흔적 표시 + 흔적 난 종목 찾기)
   데이터: ../data/trace.json (ai_trading/data/trace.py 가 매일 장 마감 뒤 만듦)
   홈: 최근 5거래일 안에 ◆ 가 찍힌 종목(없으면 최근 60일) + 지난 ◆ 전체 성적표(아무 날과 비교)
   종목 화면: 최근 60거래일 종가 선 + 거래량 막대 위 ◆1 ◆2 … + 첫 ◆ 뒤 최고·지금 */
(() => {
  let TR = null;
  fetch("../data/trace.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => {
    TR = j; const h = location.hash.slice(1).split("/")[0] || "home";
    if ((h === "home" || h === "analysis") && window.render) window.render();
  }).catch(() => {});
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + Number(x).toFixed(1) + "%";
  const md = d => d.slice(5).replace("-", ".");

  function report() {
    const s = TR && TR.stats; if (!s || !s.signal || !s.base) return "";
    return `<p class="sub tr-rep">지난 1년 ◆ ${s.signal.n}번 · ${TR.ahead}거래일 뒤 오른 비율 <b>${s.signal.win}%</b>, 평균 <b>${pct(s.signal.avg)}</b>
      <span class="tr-base">(아무 날이나 샀을 때 ${s.base.win}% · ${pct(s.base.avg)})</span><br>잘 오른 종목만 골라 보여 주지 않고 ◆ 전체를 셌어요. 대형주 78종목·약 1년 기록이라 앞으로도 같다는 보장은 없어요.</p>`;
  }

  function homeCard() {
    if (!TR || !TR.items) return "";
    const rec = TR.recent || [];
    const list = rec.length ? rec.slice(0, 5).map(it => ({ sym: it.sym, name: it.name, meta: `◆ ${it.count}번 · 마지막 ${md(it.last)} · 거래량 평소의 ${it.vr}배`, price: it.price, chg: it.chg }))
      : Object.entries(TR.items).sort((a, b) => b[1].marks.at(-1).d.localeCompare(a[1].marks.at(-1).d)).slice(0, 5)
          .map(([sym, it]) => ({ sym, name: it.name, meta: `◆ ${it.marks.length}번 · 마지막 ${md(it.marks.at(-1).d)} · 첫 ◆ 뒤 지금 ${pct(it.now_up)}`, price: it.price }));
    if (!list.length) return "";
    return `<section class="card tr-card"><div class="hd"><div><h2>큰손 매수 흔적 ◆</h2><p class="sub">${rec.length ? "최근 5거래일 안에 ◆ 가 찍힌 종목" : "최근 5거래일엔 새 ◆ 가 없어요 · 최근 60거래일에 찍힌 종목"}</p></div></div>
      <p class="sub" style="margin:2px 0 8px">조용히 옆걸음하던 종목에 평소보다 훨씬 큰 거래가 실리고, 오르며 끝났고, 기관·외국인이 순매수한 날에만 찍어요.</p>
      <ul class="list">${list.map((it, k) => `<li><button class="row" type="button" data-sym="${esc(it.sym)}">
        <span class="rank num">${k + 1}</span><span style="min-width:0"><div class="nm">${esc(it.name)}</div><div class="meta">${esc(it.meta)}</div></span>
        <span class="rt"><div class="px num">${won(it.price)}</div>${it.chg != null ? `<div class="meta num ${it.chg >= 0 ? "up" : "down"}">${(it.chg > 0 ? "+" : "") + it.chg.toFixed(2)}%</div>` : ""}</span></button></li>`).join("")}</ul>
      ${report()}<p class="sub" style="margin-top:6px">공개 시세·수급으로 계산한 참고 정보예요. 투자 권유가 아니며, ◆ 뒤에 꼭 오르지는 않아요.</p></section>`;
  }

  function chart(it) {
    const B = it.bars, n = B.c.length, W = 320, H = 170, PH = 100, VH = 50, x = k => 8 + k * (W - 16) / Math.max(1, n - 1);
    const lo = Math.min(...B.c), hi = Math.max(...B.c), y = c => 8 + (hi - c) / Math.max(1, hi - lo) * (PH - 16);
    const vmax = Math.max(...B.v) || 1, idx = Object.fromEntries(B.d.map((d, k) => [d, k]));
    const line = B.c.map((c, k) => `${k ? "L" : "M"}${x(k).toFixed(1)},${y(c).toFixed(1)}`).join("");
    const bars = B.v.map((v, k) => { const h = v / vmax * VH; return `<rect x="${(x(k) - 1.6).toFixed(1)}" y="${(H - h).toFixed(1)}" width="3.2" height="${h.toFixed(1)}" fill="var(--line)"/>`; }).join("");
    const marks = it.marks.map(m => { const k = idx[m.d]; if (k == null) return ""; const h = B.v[k] / vmax * VH, cx = x(k), cy = H - h - 9;
      return `<rect x="${(cx - 1.6).toFixed(1)}" y="${(H - h).toFixed(1)}" width="3.2" height="${h.toFixed(1)}" fill="#7c4dff"/><path d="M${cx},${cy - 6}L${cx + 5},${cy}L${cx},${cy + 6}L${cx - 5},${cy}Z" fill="#7c4dff"/><text x="${cx}" y="${cy - 9}" font-size="9" text-anchor="middle" fill="#7c4dff">${m.n}</text>`; }).join("");
    return `<svg viewBox="0 0 ${W} ${H}" class="tr-svg" role="img" aria-label="최근 60거래일 종가와 거래량, 큰손 매수 흔적 ${it.marks.length}번">
      <path d="${line}" fill="none" stroke="var(--fg)" stroke-width="1.6"/>${bars}${marks}
      <text x="8" y="${H - 2}" font-size="9" fill="var(--dim)">${md(B.d[0])}</text><text x="${W - 8}" y="${H - 2}" font-size="9" text-anchor="end" fill="var(--dim)">${md(B.d[n - 1])}</text></svg>`;
  }

  function detail(sym) {
    if (!TR || !TR.items) return "";
    const it = TR.items[sym];
    if (!it) return `<section class="card tr-card"><div class="hd"><div><h2>큰손 매수 흔적 ◆</h2><p class="sub">최근 60거래일에 찍힌 ◆ 가 없어요</p></div></div>${report()}</section>`;
    return `<section class="card tr-card"><div class="hd"><div><h2>큰손 매수 흔적 ◆ ${it.marks.length}번</h2><p class="sub">최근 60거래일 · 보라색 ◆ 가 찍힌 날의 거래량</p></div></div>
      ${chart(it)}
      <p class="tr-say">첫 ◆ ${md(it.first)} (${won(it.first_c)}원) 뒤 최고 <b class="${it.max_up >= 0 ? "up" : "down"}">${pct(it.max_up)}</b> · 지금 <b class="${it.now_up >= 0 ? "up" : "down"}">${pct(it.now_up)}</b></p>
      <ul class="tr-list">${it.marks.map(m => `<li>◆${m.n} ${md(m.d)} · 거래량 평소의 ${m.vr}배 · 종가 ${won(m.c)}원</li>`).join("")}</ul>
      ${report()}<p class="sub" style="margin-top:6px">${esc(TR.rule)}. 참고 정보이며 투자 권유가 아니에요.</p></section>`;
  }

  const css = document.createElement("style");
  css.textContent = `.tr-svg{width:100%;height:auto;margin-top:6px}.tr-say{margin:8px 0 4px;font-size:14.5px}
  .tr-list{margin:4px 0 0;padding-left:16px;font-size:12.5px;color:var(--dim)}.tr-rep{margin-top:8px;font-size:12.5px;line-height:1.55}.tr-base{color:var(--dim)}`;
  document.head.appendChild(css);
  window.Trace = { homeCard, detail };
})();
