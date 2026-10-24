/* 'AI 대결' 화면 (#vs): 상대 AI 투자자 '알파'의 실전 계좌(data/ai.json)와 나의 모의투자 계좌를 나란히 보여 준다.
   - 알파: AI 운용팀(본부장 + 직원)의 판단으로 하루 한 번 실제 종가에 사고파는 가상 1,000만 원 계좌
   - 나: game.js 모의투자 계좌(같은 1,000만 원). 아직 시작 안 했으면 시작 버튼
   index.html 이 Versus.view(SC) 를 부른다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const cls = x => (x > 0 ? "up" : x < 0 ? "down" : "flat");
  const CASH0 = 10_000_000;

  let AI = null, tried = false;
  function load() {
    if (tried) return; tried = true;
    fetch("../data/ai.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => {
      AI = d || {}; if (location.hash.startsWith("#vs")) window.dispatchEvent(new HashChangeEvent("hashchange"));
    }).catch(() => { AI = {}; });
  }

  // 알파 얼굴: PC 작업방이 사진(img/team/alpha.jpg)을 만들면 그걸 쓰고, 없으면 이 그림을 씀
  const BOT = `<svg viewBox="0 0 120 120" aria-hidden="true"><defs><linearGradient id="vsg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#cfc9ff"/><stop offset="1" stop-color="#a8d8ff"/></linearGradient></defs>
    <rect width="120" height="120" rx="60" fill="url(#vsg)"/><line x1="60" y1="18" x2="60" y2="30" stroke="#6c5ce7" stroke-width="4" stroke-linecap="round"/><circle cx="60" cy="16" r="5" fill="#ff9fb2"/>
    <rect x="26" y="30" width="68" height="56" rx="20" fill="#fff"/><rect x="34" y="42" width="52" height="24" rx="12" fill="#2d2a63"/>
    <circle cx="48" cy="54" r="5" fill="#8ff0d0"/><circle cx="72" cy="54" r="5" fill="#8ff0d0"/><path d="M50 74 q10 7 20 0" stroke="#6c5ce7" stroke-width="4" fill="none" stroke-linecap="round"/>
    <rect x="38" y="88" width="44" height="18" rx="9" fill="#fff"/><path d="M48 97 l7 -5 l6 4 l9 -8" stroke="#6c5ce7" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const face = () => `<span class="vs-face"><img src="../img/team/alpha.jpg" alt="" onerror="this.remove()">${BOT}</span>`;

  function aiStats(st) {
    const eh = st.equity_history || [];
    const eq = eh.length ? eh[eh.length - 1][1] : CASH0;
    return { eq, ret: (eq / CASH0 - 1) * 100, start: st.start_date, end: st.end_date, n: eh.length };
  }
  const dleft = end => end ? Math.max(0, Math.ceil((new Date(end + "T00:00:00+09:00") - Date.now()) / 864e5)) : null;

  function view(SC) {
    load();
    const back = `<a class="back" href="#home">‹ 홈</a>`;
    if (!AI || !SC) return `${back}<div class="card"><div class="skel" style="width:50%"></div><div class="skel"></div></div>`;
    const st = AI.state || {}, A = aiStats(st);
    const G = window.Game && Game._state ? Game._state() : null;
    const meEq = G ? (() => { let e = G.cash; for (const [s, p] of Object.entries(G.pos || {})) e += (SC.stocks[s]?.price ?? p.last ?? p.avg) * p.qty; return e; })() : null;
    const meRet = meEq == null ? null : (meEq / CASH0 - 1) * 100;
    const d = window.Team ? Team.director() : { name: "정서연", id: "theo" };
    const team = window.Team ? Team.members() : [];
    const lead = meRet == null ? "" : Math.abs(meRet - A.ret) < 0.005 ? "지금은 동점이에요" : meRet > A.ret ? `내가 알파보다 <b class="up">${(meRet - A.ret).toFixed(2)}%p</b> 앞서요` : `알파가 <b class="down">${(A.ret - meRet).toFixed(2)}%p</b> 앞서요`;

    const pos = Object.entries(st.positions || {}).map(([sym, p]) => {
      const s = SC.stocks[sym], now = s ? s.price : p.avg_price, r = (now / p.avg_price - 1) * 100;
      return `<li><button class="row" type="button" data-sym="${esc(sym)}"><span></span><span style="min-width:0"><div class="nm">${esc(s ? s.name : sym)}</div><div class="meta num">${won(p.qty)}주 · 평단 ${won(p.avg_price)}</div></span>
        <span class="rt"><div class="px num">${won(now * p.qty)}</div><div class="sc num ${cls(r)}">${pct(r)}</div></span></button></li>`;
    }).join("");
    const trades = (st.trades || []).slice(-8).reverse().map(t => {
      const s = SC.stocks[t.symbol], buy = t.side === "BUY";
      return `<li><div class="row vs-tr"><span class="${buy ? "up" : "down"} vs-side">${buy ? "매수" : "매도"}</span><span style="min-width:0"><div class="nm">${esc(s ? s.name : t.symbol)}</div>
        <div class="meta">${esc((t.time || "").slice(5, 10).replace("-", "."))} · ${esc((t.reason || "").replace(/^THEO/, d.name + " 본부장"))}</div></span>
        <span class="rt"><div class="px num">${won(t.qty)}주</div><div class="sc num">@${won(t.price)}</div></span></div></li>`;
    }).join("");

    return `${back}
    <section class="card vs-hero">
      <div class="vs-bot">${face()}<div><div class="vs-tag">AI 투자자</div><h2>알파</h2><p class="sub">${esc(d.name)} 본부장 팀의 분석을 받아 하루 한 번 실제 종가로 사고파는 AI예요. 원칙만 따르고 감정에 흔들리지 않아요.</p></div></div>
      ${team.length ? `<div class="vs-team"><span class="sub">알파의 분석팀</span><span class="vs-faces">${[d, ...team].map(m => `<img src="../img/team/${esc(m.id)}.jpg?v=4" alt="${esc(m.name)}" title="${esc(m.name)}">`).join("")}</span></div>` : ""}
    </section>
    <section class="card">
      <div class="hd"><h2>대결 현황</h2><span class="sub">${A.start ? `${esc(A.start.slice(5).replace("-", "."))} 시작${A.end ? ` · D-${dleft(A.end)}` : ""}` : "알파 계좌 준비 중"}</span></div>
      <div class="vs-board">
        <div class="vs-side-box me"><div class="k">나</div><div class="v num ${meRet == null ? "flat" : cls(meRet)}">${meRet == null ? "-" : pct(meRet)}</div><div class="c sub">${meEq == null ? "아직 시작 안 함" : won(meEq) + "원"}</div></div>
        <div class="vs-vs">VS</div>
        <div class="vs-side-box ai"><div class="k">알파</div><div class="v num ${cls(A.ret)}">${pct(A.ret)}</div><div class="c sub">${won(A.eq)}원</div></div>
      </div>
      ${lead ? `<p class="mood">${lead}</p>` : `<a class="cta" href="#game">나도 1,000만 원으로 대결 시작하기</a>`}
    </section>
    <section class="card"><div class="hd"><h2>알파가 가진 종목</h2><span class="sub">현금 ${won(st.cash_krw || 0)}원</span></div>
      ${pos ? `<ul class="list">${pos}</ul>` : '<p class="empty">지금은 보유 종목 없이 현금으로 기다리고 있어요.</p>'}</section>
    <section class="card"><div class="hd"><h2>알파의 최근 매매</h2><span class="sub">${(st.trades || []).length}회</span></div>
      ${trades ? `<ul class="list">${trades}</ul>` : '<p class="empty">아직 매매가 없어요.</p>'}</section>
    <p class="note">알파는 가상 계좌로 움직이는 AI이며, 매매 내역은 참고용이고 투자 권유가 아닙니다.</p>`;
  }

  const css = document.createElement("style");
  css.textContent = `
  .vs-hero{background:linear-gradient(135deg,#f4f2ff,#eef7ff)}
  .vs-bot{display:flex;gap:14px;align-items:center}.vs-bot h2{margin:2px 0 4px;font-size:24px}.vs-bot .sub{margin:0;line-height:1.55}
  .vs-face{position:relative;flex:none;width:84px;height:84px;border-radius:50%;overflow:hidden;box-shadow:0 8px 22px rgba(108,92,231,.25)}
  .vs-face svg,.vs-face img{position:absolute;inset:0;width:100%;height:100%}.vs-face img{object-fit:cover;object-position:50% 15%;z-index:1}
  .vs-tag{display:inline-block;font-size:11.5px;font-weight:800;color:#6c5ce7;background:#fff;border-radius:10px;padding:2px 8px}
  .vs-team{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line,#eceef6)}
  .vs-faces{display:flex}.vs-faces img{width:32px;height:32px;border-radius:50%;object-fit:cover;object-position:50% 15%;border:2px solid #fff;margin-left:-8px}
  .vs-board{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:8px;margin-top:8px}
  .vs-side-box{border-radius:16px;padding:12px;text-align:center}.vs-side-box.me{background:#fff1f4}.vs-side-box.ai{background:#eef3ff}
  .vs-side-box .k{font-weight:800;font-size:14px}.vs-side-box .v{font-size:22px;font-weight:700;margin-top:2px}.vs-side-box .c{font-size:12px}
  .vs-vs{font-weight:900;color:#6c5ce7;font-size:18px}
  .vs-tr{cursor:default;grid-template-columns:34px minmax(0,1fr) auto}.vs-side{font-size:12.5px;font-weight:700;text-align:center}
  a.cta{display:block;text-align:center;text-decoration:none;margin-top:12px}`;
  document.head.appendChild(css);

  window.Versus = { view };
})();
