/* 매일 올 이유: 출석(연속 기록) → 연구소 포인트 → 캐릭터 해금.
   - 포인트는 게임 돈(가상 1,000만 원)과 완전히 별개. 수익률 비교에 영향 없음.
   - 받는 법: 출석 +20 (연속 n일째면 +10×n 추가, 하루 최대 +100) · 모의투자 주문 +5 (하루 2번까지) · 게임 끝 +50, 알파에 이기면 +100 더
   - 쓰는 법: 남자 직원 3명(각 200)·백승현 본부장(400) 해금. 나중에 프리미엄 패스가 생기면 즉시 해금 항목.
   - 저장: aiLab.pts.v1 {pts, streak, last, log[], own[]} (이 휴대폰에만) */
(() => {
  const KEY = "aiLab.pts.v1";
  const COST = { egen: 200, teto: 200, puppy: 200, seunghyun: 400 };
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let D = { pts: 0, streak: 0, last: "", log: [], own: [], tradeDay: "", tradeN: 0, ...load() };
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
  const own = id => !COST[id] || (D.own || []).includes(id);
  function unlock(id) {
    if (own(id)) return true;
    if (D.pts < COST[id]) return false;
    D.pts -= COST[id]; D.own = [...(D.own || []), id]; D.log.unshift({ d: today(), n: -COST[id], why: "캐릭터 해금" }); save(D);
    window.dispatchEvent(new CustomEvent("aiLab:pts", { detail: { n: -COST[id], why: "해금", pts: D.pts } }));
    return true;
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
  /* 내 정보: 포인트·해금 */
  function meCard() {
    const T = window.Team;
    const items = Object.keys(COST).map(id => {
      const p = T && T.personById ? T.personById(id) : null; const nm = p ? p.name : id;
      return `<li><img src="../img/team/${id}.jpg?v=4" alt=""><span><b>${esc(nm)}</b><small>${esc(p ? p.tag : "")}</small></span>
        ${own(id) ? `<span class="pt-done">해금됨</span>` : `<button type="button" class="pt-btn" data-unlock="${id}" ${D.pts >= COST[id] ? "" : "disabled"}>${COST[id]}P로 해금</button>`}</li>`;
    }).join("");
    return `<section class="card"><div class="hd"><h2>연구소 포인트</h2><span class="pt-bal"><b>${D.pts.toLocaleString("ko-KR")}</b>P</span></div>
      <p class="sub">매일 출석 +20P(연속이면 더), 모의투자 주문 +5P, 게임 완주 +50P, 알파에 이기면 +100P. 게임 돈과는 별개예요.</p>
      <p class="sub" style="margin-top:4px">지금 <b>${D.streak}일 연속</b> 출석 중${D.log[0] ? ` · 최근: ${esc(D.log[0].why)} ${D.log[0].n > 0 ? "+" : ""}${D.log[0].n}P` : ""}</p>
      <div class="hd" style="margin-top:14px"><h2>캐릭터 해금</h2></div>
      <ul class="pt-list">${items}</ul>
      <p class="sub" style="margin-top:6px">해금한 직원·본부장은 '매니저 교체'에서 고를 수 있어요.</p></section>`;
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-unlock]"); if (!b) return;
    const id = b.dataset.unlock;
    if (unlock(id)) { flash("해금 완료! 매니저 교체에서 골라 보세요"); window.dispatchEvent(new HashChangeEvent("hashchange")); }
  });

  const r = checkin();
  if (r) { toastMsg = `+${r.n}P`; const m = `출석 +${r.n}P${r.streak > 1 ? ` (${r.streak}일 연속)` : ""}`;
    const w = setInterval(() => { if (document.querySelector(".tm-splash,#tmSheet,#guide:not([hidden])")) return; clearInterval(w); flash(m); }, 1000); } // 시작 연출·선택 화면이 끝난 뒤에

  const css = document.createElement("style");
  css.textContent = `
  .pt-strip{display:flex;align-items:center;gap:8px;margin:0 0 10px;padding:9px 14px;border-radius:16px;background:#fff;border:1px solid var(--line2,#dcd8ff);color:var(--fg,#1d2033);text-decoration:none;font-size:13.5px}
  .pt-strip .pt-fire{font-size:16px}.pt-bal{margin-left:auto;font-family:var(--f-disp);color:var(--lav-d,#6c5ce7);font-weight:700}.pt-bal b{font-size:16px}
  .pt-flash{position:fixed;left:50%;top:calc(70px + env(safe-area-inset-top));transform:translateX(-50%);z-index:70;background:#2d2a63;color:#fff;font-weight:700;font-size:14px;padding:10px 16px;border-radius:30px;box-shadow:0 10px 30px rgba(40,50,90,.3);animation:rise .3s ease both;white-space:nowrap}
  .pt-list{list-style:none;margin:8px 0 0;padding:0}.pt-list li{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--line,#eceef6)}.pt-list li:first-child{border-top:0}
  .pt-list img{width:44px;height:54px;border-radius:12px;object-fit:cover;object-position:50% 12%}.pt-list span{flex:1;min-width:0;display:flex;flex-direction:column}.pt-list small{color:var(--muted,#6b7088);font-size:12px}
  .pt-btn{border:0;border-radius:12px;padding:8px 12px;font:inherit;font-weight:700;font-size:13px;background:var(--lav-d,#6c5ce7);color:#fff}.pt-btn[disabled]{opacity:.4}
  .pt-done{font-size:12.5px;font-weight:700;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:12px;padding:6px 10px}
  .tm-card.lock{opacity:.55;position:relative}.tm-card.lock::after{content:"🔒 " attr(data-cost) "P로 해금";position:absolute;right:12px;top:10px;font-size:12px;font-weight:800;color:#fff;background:#2d2a63;border-radius:12px;padding:4px 9px}`;
  document.head.appendChild(css);

  window.Daily = { pts: () => D.pts, streak: () => D.streak, own, cost: id => COST[id] || 0, unlock, homeStrip, meCard };
})();
