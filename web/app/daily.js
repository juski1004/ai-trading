/* 매일 올 이유: 출석(연속 기록) → 연구소 포인트 → 깊은 정보 열람.
   - 포인트는 게임 돈과 별개지만, 100P로 게임 투자금 +100만 원을 살 수 있다(수익률은 넣은 돈 전체 대비라 비교에 유리해지지 않음).
   - 받는 법: 출석 +20 (연속 n일째면 +10×n 추가, 하루 최대 +100) · 모의투자 주문 +5 (하루 2번까지) · 게임 끝 +50, 알파에 이기면 +100 더
   - 쓰는 법(그날 하루 열람): 알파의 선택 미리 보기 30 · 알파 보고서 전체 20 · 실적 발표 전 리포트 20 · 매집 포착 상세 20 · 내 종목 데이터 복기 30
   - 원칙(법): 포인트는 절대 돈으로 팔지 않는다(유료 패스에 끼워 주지도 않음). 돈이 오가면 '대가를 받는 투자 정보'가 되어 유사투자자문업 신고 대상.
     종목명 자체(알파가 무엇을 샀는지)는 무료로 두고, 포인트로는 '더 깊은 분석·미리 보기'만 연다.
   - 저장: aiLab.pts.v1 {pts, streak, last, log[], has{}} (이 휴대폰에만) */
(() => {
  const KEY = "aiLab.pts.v1";
  const SHOP = { // 열람권 (그날 하루) — key 앞부분: 비용·이름
    early: [30, "알파의 선택 미리 보기", "18:10 전에 바로 보기"],
    report: [20, "알파 보고서 전체", "고른 이유·기준·기업 상황·본부장 의견 전문"],
    earn: [20, "실적 발표 전 리포트", "증권사 예상·최근 주가 반응"],
    acc: [20, "매집 포착 상세", "조용히 거래가 몰린 종목 전체 목록"],
    review: [30, "내 종목 데이터 복기", "보유 종목별 오른·내린 이유와 AI 판단 변화"],
  };
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let D = { pts: 0, streak: 0, last: "", log: [], has: {}, tradeDay: "", tradeN: 0, ...load() };
  if (!D.has) D.has = {};
  let toastMsg = "";

  function add(n, why) {
    D.pts += n; D.log.unshift({ d: today(), n, why }); D.log = D.log.slice(0, 30); save(D);
    window.dispatchEvent(new CustomEvent("aiLab:pts", { detail: { n, why, pts: D.pts } }));
  }
  function checkin() {
    const t = today(); if (D.last === t) return null;
    const y = new Date(Date.now() + 9 * 3600e3 - 864e5).toISOString().slice(0, 10);
    D.streak = D.last === y ? D.streak + 1 : 1; D.last = t;
    const bonus = Math.min(80, 10 * (D.streak - 1)), n = 20 + bonus;
    add(n, D.streak > 1 ? `출석 ${D.streak}일 연속` : "출석");
    return { n, streak: D.streak };
  }
  const kind = key => key.split(":")[0];
  const has = key => !!D.has[key];
  function buy(key) { // key = "report:2026-10-23"
    if (has(key)) return true;
    const [cost, name] = SHOP[kind(key)];
    if (D.pts < cost) { alert(`포인트가 ${cost - D.pts}P 모자라요 (지금 ${D.pts}P). 출석하고 모의투자를 하면 쌓여요.`); return false; }
    if (!confirm(`${name}을(를) ${cost}P로 열까요? (오늘 하루 볼 수 있어요)`)) return false;
    D.pts -= cost; D.has[key] = today(); D.log.unshift({ d: today(), n: -cost, why: name });
    const ks = Object.keys(D.has); if (ks.length > 60) ks.sort((a, b) => D.has[a] < D.has[b] ? -1 : 1).slice(0, ks.length - 60).forEach(k => delete D.has[k]);
    save(D); window.dispatchEvent(new CustomEvent("aiLab:pts", { detail: { n: -cost, why: name, pts: D.pts } }));
    return true;
  }
  /* 열람권이 아닌 일회성 사용 (게임 투자금 추가 등) */
  function spend(cost, why, ask) {
    if (D.pts < cost) { alert(`포인트가 ${cost - D.pts}P 모자라요 (지금 ${D.pts}P). 출석하고 모의투자를 하면 쌓여요.`); return false; }
    if (ask && !confirm(ask)) return false;
    D.pts -= cost; D.log.unshift({ d: today(), n: -cost, why }); D.log = D.log.slice(0, 30); save(D);
    window.dispatchEvent(new CustomEvent("aiLab:pts", { detail: { n: -cost, why, pts: D.pts } }));
    return true;
  }
  /* 잠긴 정보 자리: 열었으면 html, 아니면 잠금 상자 */
  function gate(key, html, teaser) {
    if (has(key)) return html;
    const [cost, name, what] = SHOP[kind(key)];
    return `<div class="pt-gate">${teaser ? `<div class="pt-tease">${teaser}</div>` : ""}<div class="pt-lock"><b>🔒 ${esc(name)}</b><span>${esc(what)}</span>
      <button type="button" class="pt-btn" data-buy="${esc(key)}">${cost}P로 열기</button><small>지금 ${D.pts.toLocaleString("ko-KR")}P · 포인트는 출석·모의투자로만 모여요</small></div></div>`;
  }

  // 게임 쪽 신호 (game.js 가 보냄)
  addEventListener("aiLab:trade", () => {
    const t = today(); if (D.tradeDay !== t) { D.tradeDay = t; D.tradeN = 0; }
    if (D.tradeN >= 2) return; D.tradeN++; add(5, "모의투자 주문"); flash("+5P 모의투자 주문");
  });
  addEventListener("aiLab:gameEnd", e => {
    const r = e.detail || {}; add(50, "게임 완주"); let m = "+50P 게임 완주";
    if (r.ai != null && r.ret > r.ai) { add(100, "알파에 승리"); m += " · +100P 알파에 승리"; }
    flash(m);
  });

  function flash(m) {
    const el = document.createElement("div"); el.className = "pt-flash"; el.textContent = m;
    document.body.appendChild(el); setTimeout(() => el.remove(), 2600);
  }

  /* 홈 위쪽 작은 띠: 오늘 출석 결과 + 포인트 */
  function homeStrip() {
    return `<a class="pt-strip" href="#me"><span class="pt-fire">${D.streak >= 3 ? "🔥" : "📅"}</span><span><b>${D.streak}일 연속</b> 출석${toastMsg ? ` · ${esc(toastMsg)}` : ""}</span><span class="pt-bal"><b>${D.pts.toLocaleString("ko-KR")}</b>P</span></a>`;
  }
  /* 내 정보: 포인트와 쓰는 곳 */
  function meCard() {
    const items = Object.entries(SHOP).map(([k, [c, n, w]]) => `<li><span><b>${esc(n)}</b><small>${esc(w)}</small></span><em>${c}P</em></li>`).join("");
    return `<section class="card"><div class="hd"><h2>연구소 포인트</h2><span class="pt-bal"><b>${D.pts.toLocaleString("ko-KR")}</b>P</span></div>
      <p class="sub">매일 출석 +20P(연속이면 더), 모의투자 주문 +5P, 게임 완주 +50P, 알파에 이기면 +100P. 게임 돈과는 별개예요.</p>
      <p class="sub" style="margin-top:4px">지금 <b>${D.streak}일 연속</b> 출석 중${D.log[0] ? ` · 최근: ${esc(D.log[0].why)} ${D.log[0].n > 0 ? "+" : ""}${D.log[0].n}P` : ""}</p>
      <div class="hd" style="margin-top:14px"><h2>포인트로 여는 정보</h2><span class="sub">그날 하루</span></div>
      <ul class="pt-list">${items}<li><span><b>게임 투자금 +100만 원</b><small>투자게임 화면에서 · 한 게임 최대 +1,500만 원</small></span><em>100P</em></li></ul>
      <p class="sub" style="margin-top:6px">포인트는 돈으로 사거나 팔 수 없어요. 알파가 무엇을 골랐는지(종목명)는 누구나 무료로 볼 수 있어요.</p></section>`;
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-buy]"); if (!b) return;
    if (buy(b.dataset.buy)) { flash("열었어요!"); window.dispatchEvent(new HashChangeEvent("hashchange")); }
  });

  const r = checkin();
  if (r) { toastMsg = `+${r.n}P`; const m = `출석 +${r.n}P${r.streak > 1 ? ` (${r.streak}일 연속)` : ""}`;
    const w = setInterval(() => { if (document.querySelector(".tm-splash,#tmSheet,#guide:not([hidden])")) return; clearInterval(w); flash(m); }, 1000); } // 시작 연출·선택 화면이 끝난 뒤에

  const css = document.createElement("style");
  css.textContent = `
  .pt-strip{display:flex;align-items:center;gap:8px;margin:0 0 10px;padding:9px 14px;border-radius:16px;background:#fff;border:1px solid var(--line2,#dcd8ff);color:var(--fg,#1d2033);text-decoration:none;font-size:13.5px}
  .pt-strip .pt-fire{font-size:16px}.pt-bal{margin-left:auto;font-family:var(--f-disp);color:var(--lav-d,#6c5ce7);font-weight:700}.pt-bal b{font-size:16px}
  .pt-flash{position:fixed;left:50%;top:calc(70px + env(safe-area-inset-top));transform:translateX(-50%);z-index:70;background:#2d2a63;color:#fff;font-weight:700;font-size:14px;padding:10px 16px;border-radius:30px;box-shadow:0 10px 30px rgba(40,50,90,.3);animation:rise .3s ease both;white-space:nowrap}
  .pt-list{list-style:none;margin:8px 0 0;padding:0}.pt-list li{display:flex;align-items:center;gap:10px;padding:9px 0;border-top:1px solid var(--line,#eceef6)}.pt-list li:first-child{border-top:0}
  .pt-list span{flex:1;min-width:0;display:flex;flex-direction:column}.pt-list small{color:var(--muted,#6b7088);font-size:12px}.pt-list em{font-style:normal;font-weight:800;color:var(--lav-d,#6c5ce7)}
  .pt-gate{position:relative}.pt-tease{filter:blur(5px);opacity:.55;pointer-events:none;user-select:none;max-height:180px;overflow:hidden}
  .pt-lock{display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;padding:16px 12px;margin-top:6px;border-radius:18px;background:linear-gradient(135deg,#f6f4ff,#f0f7ff);border:1px dashed var(--line2,#dcd8ff)}
  .pt-tease+.pt-lock{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);margin:0;background:rgba(255,255,255,.92);box-shadow:0 10px 30px rgba(40,50,90,.12)}
  .pt-lock span{font-size:13px;color:var(--muted,#6b7088)}.pt-lock small{font-size:11.5px;color:var(--muted,#6b7088)}
  .pt-btn{border:0;border-radius:12px;padding:8px 12px;font:inherit;font-weight:700;font-size:13px;background:var(--lav-d,#6c5ce7);color:#fff}.pt-btn[disabled]{opacity:.4}
  .pt-done{font-size:12.5px;font-weight:700;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:12px;padding:6px 10px}
`;
  document.head.appendChild(css);

  window.Daily = { pts: () => D.pts, streak: () => D.streak, has, buy, spend, gate, today, homeStrip, meCard };
})();
