/* AI 분석팀의 적극적인 알림 (앱).
   - 2026-11-24: AI 대결·모의투자 게임을 없애고 → 이번 주 본부장 추천 종목 손절·익절 근접, 관심 종목(★) 판단·큰 움직임 알림으로
   - 화면에 뜨는 알림(토스트)은 홈에서만, 하루 2개까지(손절·목표가·알파의 선택이 우선). 나머지는 홈 'AI 알림' 카드와 종 버튼에만.
   - 내 투자게임 보유 종목: 게임 규칙(목표 +10%·손절 −5%)에 닿으면 알려 주고, AI 판단이 '부정'으로 바뀌면 알려 줌
   - 실적 발표가 다가온 종목(data/earnings.json): 증권사 예상과 일정 안내
   - 알파의 선택: 알파 팀이 오늘 게임 계좌에 담은 종목(pick.json) 또는 AI 점수 상위 '긍정' 종목 (데이터 요약)
   법: 사용자에게 사고팔라고 권하는 문장은 쓰지 않는다. 모든 종목 언급은 게임 상대(알파)의 행동이거나 데이터 요약이다.
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
  const RIV = () => (window.Team && Team.rivals ? { ...Team.rivals().dir, role: "알파 팀 본부장" } : { id: "seunghyun", name: "백승현", role: "알파 팀 본부장" });
  const QUOTA = "aiLab.advq.v1", MAXQ = 2; // 하루에 화면에 띄우는 알림 수
  const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const quota = () => { const q = load(QUOTA, {}); return q.d === today() ? q.n : 0; };
  const useQuota = () => { const q = load(QUOTA, {}); save(QUOTA, { d: today(), n: (q.d === today() ? q.n : 0) + 1 }); };
  const SEEN = "aiLab.seen.v1";
  const jo = (w, a, b) => { const c = String(w).charCodeAt(String(w).length - 1) - 0xac00; return w + (c >= 0 && c < 11172 ? (c % 28 ? a : b) : /[0136789lmnr]$/i.test(w) ? a : b); }; // 받침 따라 이/가

  let EA = null, PK = null, ITEMS = [], queue = [], ready = false;
  Promise.all([get("report/track.json"), get("earnings.json"), get("pick.json")]).then(([a, e, p]) => { window.__TRACK = window.__TRACK || a; EA = e; PK = p; ready = true; build(); });

  function build() {
    const SC = window.__SC; if (!ready || !SC) return;
    const S = SC.stocks, out = [];
    const add = (key, who, msg, go) => out.push({ key, who, msg, go });

    // 1) 이번 주 본부장 추천 종목 (2026-11-24 사용자: 추천 따라 하기 모의 성적) — 손절·익절에 가까워지면 알림
    const TK = window.__TRACK, wk = TK && TK.weeks && TK.weeks[0];
    if (wk && !wk.done) wk.picks.forEach(p => {
      const sym = Object.keys(S).find(k => S[k].code === p.code), x = sym && S[sym]; if (!x) return;
      const r = (x.price / p.entry - 1) * 100, D = DIR(), go = "#track";
      if (p.target && x.price >= p.target) add(`tp:${p.code}:${SC.date}`, D, `이번 주 추천 <b>${esc(jo(p.name, "이", "가"))}</b> 익절가 ${won(p.target)}원에 닿았어요(${pct(r)}). 모의 주문은 익절로 체결됐어요.`, go);
      else if (p.stop && x.price <= p.stop) add(`sl:${p.code}:${SC.date}`, D, `이번 주 추천 <b>${esc(jo(p.name, "이", "가"))}</b> 손절가 ${won(p.stop)}원에 닿았어요(${pct(r)}). 모의 주문은 계획대로 손절됐어요.`, go);
      else if (p.stop && x.price <= p.stop * 1.02) add(`sl2:${p.code}:${SC.date}`, D, `이번 주 추천 <b>${esc(jo(p.name, "이", "가"))}</b> 손절가 ${won(p.stop)}원까지 ${((x.price / p.stop - 1) * 100).toFixed(1)}% 남았어요.`, go);
    });
    // 2) 관심 종목(★): AI 판단이 '부정'이면 알림
    load("aiLab.watch.v1", []).forEach(s => {
      const x = S[s]; if (!x) return;
      if (x.label === "부정") add(`neg:${s}:${SC.date}`, P("RAY"), `관심 종목 <b>${esc(x.name)}</b>의 AI 판단이 '부정'이에요. 분석 화면에서 이유를 확인해 보세요.`, "#analysis/" + encodeURIComponent(s));
      if (Math.abs(x.chg) >= 5) add(`mv:${s}:${SC.date}`, P("OSCAR"), `관심 종목 <b>${esc(x.name)}</b> 오늘 ${pct(x.chg)} 움직였어요.`, "#analysis/" + encodeURIComponent(s));
    });
    // 3) 실적 발표 임박: 미리 판단
    if (EA && EA.items) {
      const held = new Set(load("aiLab.watch.v1", []));
      const list = [...EA.items].sort((a, b) => (held.has(b.sym) - held.has(a.sym)) || ((b.tone === "호재") - (a.tone === "호재")) || Math.abs(b.growth || 0) - Math.abs(a.growth || 0)).slice(0, 3);
      list.forEach(e => add(`ea:${e.sym}:${e.date}`, P("OSCAR"),
        `<b>${esc(e.name)}</b> ${+e.date.slice(5, 7)}월 ${+e.date.slice(8)}일${e.guess ? "경" : ""} 실적 발표 예정이에요(${e.days}일 뒤). 증권사 예상과 최근 주가 반응은 홈 '실적 발표' 리포트에서 볼 수 있어요.`, "#analysis/" + encodeURIComponent(e.sym)));
    }
    // 4) AI 점수 상위 '긍정' 종목 (데이터 요약)
    Object.entries(S).filter(([, x]) => x.label === "긍정").sort((a, b) => b[1].score - a[1].score).slice(0, 2).forEach(([s, x]) =>
      add(`buy:${s}:${SC.date}`, P("MILES"), `<b>${esc(x.name)}</b> AI 점수 ${Math.round((x.score + 1) * 50)}점으로 '긍정'이에요 (참고 손절가 ${won(x.stop)}원).`, "#analysis/" + encodeURIComponent(s)));

    const rank = k => (/^(tp|sl|neg)/.test(k) ? 0 : /^ai/.test(k) ? 1 : /^ea/.test(k) ? 2 : 3);
    ITEMS = out.sort((a, b) => rank(a.key) - rank(b.key));
    const seen = load(SEEN, {});
    const left = Math.max(0, MAXQ - quota());
    queue = out.filter(x => !seen[x.key] && /^(tp|sl|neg)/.test(x.key)).slice(0, left); // 급한 것만, 하루 2개까지
    tick();
    const box = document.getElementById("adv-home"); if (box) box.outerHTML = homeCard();
  }

  /* 한 장씩 띄우기 (브리핑 알림·시작 연출과 겹치지 않게) */
  function tick() {
    if (document.getElementById("advToast") || !queue.length) return;
    if ((location.hash.slice(1) || "home").split("/")[0] !== "home") return; // 홈에서만 띄움 (다른 화면을 가리지 않게)
    if (document.querySelector(".tm-splash,#tmSheet,#rpToast,.bover,.tour-on,#tourAsk")) return;
    const x = queue[0], el = document.createElement("div");
    el.id = "advToast"; el.className = "adv-toast"; el.setAttribute("role", "status");
    el.innerHTML = `<img src="../img/team/${esc(x.who.id)}.jpg?v=4" alt=""><div class="adv-b"><div class="adv-w"><b>${esc(x.who.name)}</b> ${esc(x.who.role || "")}</div><p>${x.msg}</p>
      <div class="adv-a"><button type="button" data-adv="go">자세히</button><button type="button" data-adv="next">${queue.length > 1 ? "다음" : "닫기"}</button></div></div>`;
    document.body.appendChild(el);
  }
  function done(go) {
    const x = queue.shift(); if (!x) return;
    const seen = load(SEEN, {}); seen[x.key] = 1; useQuota(); const keys = Object.keys(seen); if (keys.length > 400) keys.slice(0, 200).forEach(k => delete seen[k]); save(SEEN, seen);
    document.getElementById("advToast")?.remove();
    if (go) { location.hash = x.go; queue = []; } else setTimeout(tick, 250);
  }
  document.addEventListener("click", e => { const b = e.target.closest("[data-adv]"); if (b) done(b.dataset.adv === "go"); });
  addEventListener("hashchange", () => { if ((location.hash.slice(1) || "home").split("/")[0] !== "home") document.getElementById("advToast")?.remove(); }); // 홈을 떠나면 내려감 (안 본 것으로 두어 다음에 홈에서 다시 띄움)
  setInterval(() => { if (!ITEMS.length) build(); else tick(); }, 2500);

  const li = x => `<li><a href="${x.go}"><img src="../img/team/${esc(x.who.id)}.jpg?v=4" alt=""><span><b>${esc(x.who.name)}</b> ${x.msg}</span></a></li>`;
  function homeCard() {
    if (!ITEMS.length) return `<div id="adv-home"></div>`;
    return `<section class="card adv-home" id="adv-home"><div class="hd"><h2>AI 알림</h2><span class="sub">데이터 안내 · 투자 권유 아님</span></div>
      <ul class="adv-list">${ITEMS.slice(0, 4).map(li).join("")}</ul>${ITEMS.length > 4 ? `<details class="adv-more"><summary>알림 ${ITEMS.length - 4}개 더 보기</summary><ul class="adv-list">${ITEMS.slice(4, 12).map(li).join("")}</ul></details>` : ""}</section>`;
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
  .adv-list li:first-child a{border-top:0}
  .adv-more summary{list-style:none;cursor:pointer;text-align:center;padding:10px 0 2px;color:var(--lav-d,#6c5ce7);font-weight:700;font-size:13.5px}.adv-more summary::-webkit-details-marker{display:none}.adv-more[open] summary{display:none}.adv-list img{width:36px;height:44px;border-radius:10px;object-fit:cover;object-position:50% 12%;flex:none}`;
  document.head.appendChild(css);

  window.Advise = { homeCard, refresh: build };
})();
