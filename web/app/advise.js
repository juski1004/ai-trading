/* AI 운용팀의 적극적인 알림 (앱).
   - AI 대결 중이면: AI 실전 계좌(data/ai.json)가 새로 사고판 내역 + 지금 주식·현금·수익률
   - 내 투자게임 보유 종목: 목표가(+10%)·손절가(−5%)에 다다르면 매도 권유, AI 판단이 '부정'이면 매도 검토 권유
   - 실적 발표가 다가온 종목(data/earnings.json): 증권사 예상으로 미리 판단해 '발표 전 진입' 또는 '피하기' 권유
   - 매수 권유: 오늘의 추천(pick.json) 또는 AI 점수 상위 '긍정' 종목
   새 알림은 화면 아래에 한 장씩 띄우고(이미 본 것은 다시 안 띄움), 홈 맨 위 'AI 알림' 카드에 모아 둔다.
   참고 의견이며 투자 권유가 아니다. index.html 이 Advise.homeCard() 를 부른다. */
(() => {
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const load = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const get = f => fetch("../data/" + f, { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const P = a => (window.Team ? Team.person(a) : { id: a.toLowerCase(), name: a, role: "" });
  const DIR = () => (window.Team ? { ...Team.director(), role: "본부장" } : { id: "theo", name: "정서연", role: "본부장" });
  const SEEN = "aiLab.seen.v1";
  const jo = (w, a, b) => { const c = String(w).charCodeAt(String(w).length - 1) - 0xac00; return w + (c >= 0 && c < 11172 ? (c % 28 ? a : b) : /[0136789lmnr]$/i.test(w) ? a : b); }; // 받침 따라 이/가

  let AI = null, EA = null, PK = null, ITEMS = [], queue = [], ready = false;
  Promise.all([get("ai.json"), get("earnings.json"), get("pick.json")]).then(([a, e, p]) => { AI = a; EA = e; PK = p; ready = true; build(); });

  function build() {
    const SC = window.__SC; if (!ready || !SC) return;
    const S = SC.stocks, nm = s => (S[s] ? S[s].name : s), G = load("aiLab.game.v1", null), out = [];
    const add = (key, who, msg, go) => out.push({ key, who, msg, go });

    // 1) AI 대결: AI 실전 계좌 매매 알림 + 잔고
    if (G && AI && AI.state) {
      const st = AI.state, since = G.start || "";
      (st.trades || []).filter(t => t.time.slice(0, 10) >= since).slice(-4).forEach(t => {
        const buy = t.side === "BUY";
        add(`ai:${t.time}:${t.symbol}`, DIR(), `AI 운용팀이 <b>${esc(nm(t.symbol))}</b> ${won(t.qty)}주를 ${won(t.price)}원에 ${buy ? "매수" : "매도"}했습니다.${t.realized_krw ? ` 실현 손익 ${won(t.realized_krw)}원입니다.` : ""}`, "#game");
      });
      const stock = Object.entries(st.positions || {}).reduce((a, [s, p]) => a + p.qty * (S[s] ? S[s].price : p.avg_price), 0), cash = st.cash_krw || 0;
      const eqh = st.equity_history || [], base = eqh.length ? eqh[0][1] : 10_000_000, r = ((stock + cash) / base - 1) * 100;
      add(`aibal:${SC.date}`, DIR(), `AI 계좌 현황입니다. 주식 <b>${won(stock)}원</b>, 현금 <b>${won(cash)}원</b>, 수익률 <b class="${r >= 0 ? "up" : "down"}">${pct(r)}</b>입니다.`, "#game");
    }
    // 2) 내 보유 종목: 목표가·손절가·AI 판단
    if (G && G.pos) Object.entries(G.pos).forEach(([s, p]) => {
      const x = S[s]; if (!x || !p.avg) return;
      const r = (x.price / p.avg - 1) * 100, L = P("LLOYD");
      if (r >= 10) add(`tp:${s}:${SC.date}`, L, `<b>${esc(jo(x.name, "이", "가"))}</b> 목표가(+10%)에 다다랐습니다(${pct(r)}). 일부 매도로 수익 실현을 권합니다.`, "#game/" + encodeURIComponent(s));
      else if (r >= 8) add(`tp8:${s}:${SC.date}`, L, `<b>${esc(jo(x.name, "이", "가"))}</b> 목표가에 거의 다다랐습니다(${pct(r)}). 매도 준비를 권합니다.`, "#game/" + encodeURIComponent(s));
      else if (r <= -5) add(`sl:${s}:${SC.date}`, L, `<b>${esc(jo(x.name, "이", "가"))}</b> 손절가(−5%)에 다다랐습니다(${pct(r)}). 원칙대로 매도를 권합니다.`, "#game/" + encodeURIComponent(s));
      else if (r <= -4) add(`sl4:${s}:${SC.date}`, L, `<b>${esc(jo(x.name, "이", "가"))}</b> 손절가에 가까워졌습니다(${pct(r)}). 손절 주문을 확인하시길 권합니다.`, "#game/" + encodeURIComponent(s));
      if (x.label === "부정") add(`neg:${s}:${SC.date}`, P("RAY"), `보유 중인 <b>${esc(x.name)}</b>의 AI 판단이 '부정'으로 바뀌었습니다. 비중 축소를 검토하시길 권합니다.`, "#analysis/" + encodeURIComponent(s));
    });
    // 3) 실적 발표 임박: 미리 판단
    if (EA && EA.items) {
      const held = new Set(Object.keys((G && G.pos) || {}));
      const list = [...EA.items].sort((a, b) => (held.has(b.sym) - held.has(a.sym)) || ((b.tone === "호재") - (a.tone === "호재")) || Math.abs(b.growth || 0) - Math.abs(a.growth || 0)).slice(0, 3);
      list.forEach(e => add(`ea:${e.sym}:${e.date}`, P("OSCAR"),
        `<b>${esc(e.name)}</b> ${+e.date.slice(5, 7)}월 ${+e.date.slice(8)}일${e.guess ? "경" : ""} 실적 발표 예정입니다(${e.days}일 뒤). ${e.eps ? `증권사 예상 EPS ${won(e.eps)}원. ` : ""}${esc(e.view)}`, "#analysis/" + encodeURIComponent(e.sym)));
    }
    // 4) 매수 권유
    if (PK && PK.found && PK.date === SC.date) add(`pick:${PK.date}`, P("MILES"), `오늘의 추천 <b>${esc(PK.name)}</b>, 1차 ${won(PK.plan.entry)}원 진입을 권합니다. 손절 ${won(PK.plan.stop)}원, 1차 목표 ${won(PK.plan.target)}원입니다.`, "#pick");
    else Object.entries(S).filter(([, x]) => x.label === "긍정").sort((a, b) => b[1].score - a[1].score).slice(0, 2).forEach(([s, x]) =>
      add(`buy:${s}:${SC.date}`, P("MILES"), `<b>${esc(x.name)}</b> AI 점수 ${Math.round((x.score + 1) * 50)}점으로 '긍정'입니다. ${won(x.price)}원 근처에서 분할 매수를 권합니다(손절 ${won(x.stop)}원).`, "#analysis/" + encodeURIComponent(s)));

    const rank = k => (/^(tp|sl|neg)/.test(k) ? 0 : /^ai/.test(k) ? 1 : /^ea/.test(k) ? 2 : 3);
    ITEMS = out.sort((a, b) => rank(a.key) - rank(b.key));
    const seen = load(SEEN, {});
    queue = out.filter(x => !seen[x.key]);
    tick();
    const box = document.getElementById("adv-home"); if (box) box.outerHTML = homeCard();
  }

  /* 한 장씩 띄우기 (브리핑 알림·시작 연출과 겹치지 않게) */
  function tick() {
    if (document.getElementById("advToast") || !queue.length) return;
    if (document.querySelector(".tm-splash,#tmSheet,#rpToast,.bover")) return;
    const x = queue[0], el = document.createElement("div");
    el.id = "advToast"; el.className = "adv-toast"; el.setAttribute("role", "status");
    el.innerHTML = `<img src="../img/team/${esc(x.who.id)}.jpg?v=4" alt=""><div class="adv-b"><div class="adv-w"><b>${esc(x.who.name)}</b> ${esc(x.who.role || "")} <em>알림 ${ITEMS.length - queue.length + 1}/${ITEMS.length}</em></div><p>${x.msg}</p>
      <div class="adv-a"><button type="button" data-adv="go">자세히</button><button type="button" data-adv="next">${queue.length > 1 ? "다음" : "닫기"}</button></div></div>`;
    document.body.appendChild(el);
  }
  function done(go) {
    const x = queue.shift(); if (!x) return;
    const seen = load(SEEN, {}); seen[x.key] = 1; const keys = Object.keys(seen); if (keys.length > 400) keys.slice(0, 200).forEach(k => delete seen[k]); save(SEEN, seen);
    document.getElementById("advToast")?.remove();
    if (go) { location.hash = x.go; queue = []; } else setTimeout(tick, 250);
  }
  document.addEventListener("click", e => { const b = e.target.closest("[data-adv]"); if (b) done(b.dataset.adv === "go"); });
  setInterval(() => { if (!ITEMS.length) build(); else tick(); }, 2500);

  function homeCard() {
    if (!ITEMS.length) return `<div id="adv-home"></div>`;
    return `<section class="card adv-home" id="adv-home"><div class="hd"><h2>AI 알림</h2><span class="sub">참고 의견 · 투자 권유 아님</span></div>
      <ul class="adv-list">${ITEMS.slice(0, 8).map(x => `<li><a href="${x.go}"><img src="../img/team/${esc(x.who.id)}.jpg?v=4" alt=""><span><b>${esc(x.who.name)}</b> ${x.msg}</span></a></li>`).join("")}</ul></section>`;
  }

  const css = document.createElement("style");
  css.textContent = `
  .adv-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(var(--nav-h,66px) + 28px + env(safe-area-inset-bottom));z-index:45;width:min(560px,calc(100% - 24px));display:flex;gap:12px;align-items:flex-start;background:#fff;border:1px solid var(--line2,#dcd8ff);border-radius:22px;padding:14px;box-shadow:0 18px 50px rgba(40,50,90,.25);animation:rise .3s ease both}
  .adv-toast img{width:52px;height:64px;border-radius:14px;object-fit:cover;object-position:50% 12%;flex:none}
  .adv-b{min-width:0;flex:1}.adv-w{font-size:13px}.adv-w em{font-style:normal;color:var(--muted,#6b7088);margin-left:6px;font-size:12px}
  .adv-b p{margin:4px 0 0;font-size:14.5px;line-height:1.55}
  .adv-a{display:flex;gap:8px;justify-content:flex-end;margin-top:8px}.adv-a button{border:0;border-radius:12px;padding:8px 14px;font:inherit;font-weight:700;font-size:13px;background:var(--lav-s,#efedff);color:var(--lav-d,#6c5ce7)}
  .adv-a button[data-adv=go]{background:var(--gold-g);color:var(--ink,#2d2a63)}
  .adv-list{list-style:none;margin:0;padding:0}.adv-list a{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--line,#eceef6);color:var(--fg,#1d2033);text-decoration:none;font-size:14px;line-height:1.55}
  .adv-list li:first-child a{border-top:0}.adv-list img{width:36px;height:44px;border-radius:10px;object-fit:cover;object-position:50% 12%;flex:none}`;
  document.head.appendChild(css);

  window.Advise = { homeCard, refresh: build };
})();
