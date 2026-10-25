/* 매일 올 이유: 출석(연속 기록) → 연구소 포인트 → 깊은 정보 열람.
   - 포인트는 게임 돈과 별개지만, 100P로 게임 투자금 +100만 원을 살 수 있다(수익률은 넣은 돈 전체 대비라 비교에 유리해지지 않음).
   - 받는 법: 출석 +20 (연속 n일째면 +10×n 추가, 하루 최대 +100) · 모의투자 주문 +5 (하루 2번까지) · 게임 끝 +50, 알파에 이기면 +100 더
   - 쓰는 법(그날 하루 열람): 알파의 선택 미리 보기 30 · 알파 보고서 전체 20 · 실적 발표 전 리포트 20 · 매집 포착 상세 20 · 내 종목 데이터 복기 30
   - 원칙(법): 포인트는 절대 돈으로 팔지 않는다(유료 패스에 끼워 주지도 않음). 돈이 오가면 '대가를 받는 투자 정보'가 되어 유사투자자문업 신고 대상.
     종목명 자체(알파가 무엇을 샀는지)는 무료로 두고, 포인트로는 '더 깊은 분석·미리 보기'만 연다.
   - 시즌 보상(지난 달 랭킹): 1위 +500 · 3위 안 +300 · 상위 10% +200 · 참여 +50, 시즌 배지
   - 친구 초대: 내 코드로 친구가 시작하면 나 +100P(최대 30명), 친구 +100P (서버가 기기당 한 번만 인정)
   - 저장: aiLab.pts.v1 {pts, streak, last, log[], has{}, uid, badges[], seasons[], invUsed, invPaid} (이 휴대폰에만) */
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
  if (!D.uid) { D.uid = [...crypto.getRandomValues(new Uint8Array(10))].map(b => (b % 36).toString(36)).join("") + Date.now().toString(36).slice(-4); save(D); }
  const myCode = () => D.uid.slice(0, 8);
  const server = fetch("server.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => j && j.url).catch(() => null);
  const api = async (path, body) => { const u = await server; if (!u) throw new Error("서버 준비 중");
    const r = await fetch(u + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
    const j = await r.json().catch(() => ({})); if (!r.ok) throw Object.assign(new Error(j.error || r.status), { code: j.error }); return j; };
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

  /* 지난 시즌 보상 (Push.getBoard 가 지난 시즌 내 순위를 받아 오면 한 번만) */
  function seasonReward(L) {
    if (!L || !L.season || (D.seasons || []).includes(L.season)) return;
    const top10 = Math.max(1, Math.ceil(L.total * 0.1)), n = L.rank === 1 ? 500 : L.rank <= 3 ? 300 : L.rank <= top10 ? 200 : 50;
    D.seasons = [...(D.seasons || []), L.season]; D.badges = [...(D.badges || []), { ...L }];
    add(n, `${+L.season.slice(5)}월 시즌 ${L.rank}위`);
    flash(`${+L.season.slice(5)}월 시즌 ${L.rank}위 · +${n}P 시즌 배지 획득!`);
  }
  const badgeHtml = b => `<span class="pt-badge">${b.rank === 1 ? "🥇" : b.rank === 2 ? "🥈" : b.rank === 3 ? "🥉" : "🎖️"} ${+b.season.slice(5)}월 ${b.league === "pro" ? "일반" : "새내기"} ${b.rank}위<small>/${b.total}명</small></span>`;

  /* 친구 초대 */
  let invMsg = "";
  async function redeem(code) {
    code = String(code || "").trim().toLowerCase();
    if (!/^[a-z0-9]{6,10}$/.test(code)) { invMsg = "초대 코드를 다시 확인해 주세요."; return false; }
    if (code === myCode()) { invMsg = "내 코드는 쓸 수 없어요."; return false; }
    if (D.invUsed) { invMsg = "초대 코드는 한 번만 쓸 수 있어요."; return false; }
    try { await api("/invite", { code, id: D.uid }); D.invUsed = code; save(D); add(100, "친구 초대 코드"); flash("초대 코드 확인! +100P"); invMsg = ""; return true; }
    catch (e) { invMsg = e.code === "already" ? "이 기기는 이미 초대 코드를 썼어요." : e.code === "full" ? "이 코드는 초대 인원이 다 찼어요." : "지금은 확인할 수 없어요. 잠시 뒤 다시 해 주세요."; if (e.code === "already") { D.invUsed = code; save(D); } return false; }
  }
  async function checkInvites() { // 내 코드로 시작한 친구 수만큼 보상
    try { const { count } = await api("/invite?code=" + myCode()); const paid = D.invPaid || 0;
      if (count > paid) { const n = (count - paid) * 100; D.invPaid = count; add(n, `친구 ${count - paid}명 초대`); flash(`친구 ${count - paid}명이 내 코드로 시작했어요 · +${n}P`); }
    } catch (e) {}
  }
  const inviteLink = () => `${location.origin}${location.pathname.replace(/[^/]*$/, "")}?ref=${myCode()}`;
  async function shareInvite() {
    const text = `AI 투자연구소 — 퇴근길 5분 종가 스윙 모의투자 게임. 내 초대 코드 ${myCode()} 를 넣으면 100P를 받아요.`;
    if (navigator.share) { try { await navigator.share({ title: "AI 투자연구소 초대", text, url: inviteLink() }); return; } catch (e) { if (e.name === "AbortError") return; } }
    try { await navigator.clipboard.writeText(`${text} ${inviteLink()}`); flash("초대 링크를 복사했어요"); } catch (e) { prompt("이 링크를 친구에게 보내 주세요", inviteLink()); }
  }
  // 초대 링크로 들어온 경우 (?ref=코드) → 동의·호칭을 마친 뒤 자동 확인
  const ref = new URLSearchParams(location.search).get("ref");
  if (ref && !D.invUsed) { const w = setInterval(() => { if (document.querySelector(".tm-splash,#tmSheet")) return; clearInterval(w); redeem(ref); }, 1500); }

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
      <p class="sub" style="margin-top:6px">포인트는 돈으로 사거나 팔 수 없어요. 알파가 무엇을 골랐는지(종목명)는 누구나 무료로 볼 수 있어요.</p>
      ${(D.badges || []).length ? `<div class="hd" style="margin-top:14px"><h2>시즌 배지</h2></div><div class="pt-badges">${D.badges.map(badgeHtml).join("")}</div>` : ""}</section>
    <section class="card"><div class="hd"><h2>친구 초대</h2><span class="sub">친구 1명당 +100P</span></div>
      <p class="sub">내 초대 코드로 친구가 시작하면 나도 친구도 100P씩 받아요 (최대 30명).</p>
      <div class="pt-code"><b>${myCode()}</b><button type="button" class="pt-btn" data-inv="share">초대 링크 보내기</button></div>
      ${D.invPaid ? `<p class="sub">지금까지 <b>${D.invPaid}명</b>이 내 코드로 시작했어요.</p>` : ""}
      ${D.invUsed ? `<p class="sub" style="margin-top:8px">받은 초대 코드: ${esc(D.invUsed)} ✓</p>` : `<form class="pt-redeem" data-inv-form><input name="code" maxlength="10" placeholder="친구의 초대 코드" autocomplete="off" aria-label="초대 코드"><button type="submit" class="pt-btn">받기</button></form>`}
      ${invMsg ? `<p class="g-msg" role="status">${esc(invMsg)}</p>` : ""}</section>`;
  }
  document.addEventListener("click", e => { if (e.target.closest('[data-inv="share"]')) shareInvite(); });
  document.addEventListener("submit", async e => {
    const f = e.target.closest("[data-inv-form]"); if (!f) return; e.preventDefault();
    await redeem(f.code.value); window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  addEventListener("hashchange", () => { if (location.hash === "#me") checkInvites(); });
  if (location.hash === "#me") setTimeout(checkInvites, 1500);
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
  .pt-badges{display:flex;flex-wrap:wrap;gap:6px}.pt-badge{display:inline-flex;align-items:baseline;gap:3px;padding:6px 10px;border-radius:14px;background:#fff7e0;border:1px solid #ffe2a0;font-size:13px;font-weight:700}.pt-badge small{font-weight:500;color:var(--muted,#6b7088)}
  .pt-code{display:flex;align-items:center;gap:10px;margin:10px 0 6px}.pt-code b{flex:1;font-family:var(--f-disp);font-size:22px;letter-spacing:.12em;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:12px;padding:8px 12px;text-align:center}
  .pt-redeem{display:flex;gap:8px;margin-top:10px}.pt-redeem input{flex:1;min-width:0;font:inherit;padding:9px 12px;border-radius:12px;border:1.5px solid var(--line2,#dcd8ff)}
  .pt-gate{position:relative}.pt-tease{filter:blur(5px);opacity:.55;pointer-events:none;user-select:none;max-height:180px;overflow:hidden}
  .pt-lock{display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;padding:16px 12px;margin-top:6px;border-radius:18px;background:linear-gradient(135deg,#f6f4ff,#f0f7ff);border:1px dashed var(--line2,#dcd8ff)}
  .pt-tease+.pt-lock{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);margin:0;background:rgba(255,255,255,.92);box-shadow:0 10px 30px rgba(40,50,90,.12)}
  .pt-lock span{font-size:13px;color:var(--muted,#6b7088)}.pt-lock small{font-size:11.5px;color:var(--muted,#6b7088)}
  .pt-btn{border:0;border-radius:12px;padding:8px 12px;font:inherit;font-weight:700;font-size:13px;background:var(--lav-d,#6c5ce7);color:#fff}.pt-btn[disabled]{opacity:.4}
  .pt-done{font-size:12.5px;font-weight:700;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:12px;padding:6px 10px}
`;
  document.head.appendChild(css);

  window.Daily = { pts: () => D.pts, streak: () => D.streak, has, buy, spend, gate, today, homeStrip, meCard, seasonReward, badges: () => D.badges || [], code: myCode };
})();
