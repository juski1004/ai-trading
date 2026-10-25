/* 'AI 대결' 화면 (#vs): 내 팀 vs 알파 팀.
   - 내 팀: 내가 고른 본부장 + 직원 (= 내 모의투자 계좌, game.js)
   - 알파 팀: 내가 고르지 않은 본부장·직원. 내 게임 시작일 다음 날부터 나와 같은 돈(현금)으로 시작해
     AI 투자자 '알파'(data/ai.json)의 매매를 같은 비중으로 따라 하는 계좌 (Game.alphaClone). 시작 전 매매·보유는 없음
   - 총자산·현금·주식 평가액·손익·수익률, 줄다리기 막대와 수익률 경주 그래프로 누가 이기고 있는지 보여 준다.
   - 승패는 같은 기간(내 게임 시작일부터)으로 비교한다. 결과를 인스타 등에 올릴 공유 이미지로 만들 수 있다.
   index.html 이 Versus.view(SC) 를, deck.js 가 Versus.summary(SC) 를 부른다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => { const t = Math.abs(x) < 0.005 ? "0.00" : x.toFixed(2); return (x >= 0.005 ? "+" : "") + t + "%"; };
  const sgn = n => (n >= 0 ? "+" : "−") + won(Math.abs(n));
  const cls = x => (x >= 0.005 ? "up" : x <= -0.005 ? "down" : "flat");
  const CASH0 = 10_000_000, START0 = 5_000_000; // 예전 게임 시작금 · 지금 게임 시작금 (알파 팀도 같은 돈)
  const face = id => `../img/team/${id}.jpg?v=4`;

  let AI = null, tried = false;
  function load() {
    if (tried) return; tried = true;
    fetch("../data/ai.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => {
      AI = d || {}; window.dispatchEvent(new HashChangeEvent("hashchange"));
    }).catch(() => { AI = {}; });
  }

  // 알파 마스코트: PC 작업방이 사진(img/team/alpha.jpg)을 넣으면 사진, 없으면 그림
  const BOT = `<svg viewBox="0 0 120 120" aria-hidden="true"><defs><linearGradient id="vsg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#cfc9ff"/><stop offset="1" stop-color="#a8d8ff"/></linearGradient></defs>
    <rect width="120" height="120" rx="60" fill="url(#vsg)"/><line x1="60" y1="18" x2="60" y2="30" stroke="#6c5ce7" stroke-width="4" stroke-linecap="round"/><circle cx="60" cy="16" r="5" fill="#ff9fb2"/>
    <rect x="26" y="30" width="68" height="56" rx="20" fill="#fff"/><rect x="34" y="42" width="52" height="24" rx="12" fill="#2d2a63"/>
    <circle cx="48" cy="54" r="5" fill="#8ff0d0"/><circle cx="72" cy="54" r="5" fill="#8ff0d0"/><path d="M50 74 q10 7 20 0" stroke="#6c5ce7" stroke-width="4" fill="none" stroke-linecap="round"/>
    <rect x="38" y="88" width="44" height="18" rx="9" fill="#fff"/><path d="M48 97 l7 -5 l6 4 l9 -8" stroke="#6c5ce7" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const bot = (sz = 44) => `<span class="vs-bot" style="width:${sz}px;height:${sz}px"><img src="../img/team/alpha.jpg" alt="" onerror="this.remove()">${BOT}</span>`;

  /* ---------- 계산 ---------- */
  function sides(SC) {
    const st = (AI && AI.state) || {}, G = window.Game && Game._state ? Game._state() : null;
    const so = sym => (window.stockOf ? window.stockOf(sym) : SC.stocks[sym]), px = (sym, fb) => { const s = so(sym); return s ? s.price : fb; };
    const start = G ? G.start : null;
    // 내 계좌
    const mPos = G ? Object.entries(G.pos || {}).map(([sym, p]) => ({ sym, name: p.name, qty: p.qty, avg: p.avg, now: px(sym, p.last ?? p.avg) })) : [];
    const mStock = mPos.reduce((s, p) => s + p.qty * p.now, 0), mEq = G ? G.cash + mStock : null;
    const mB0 = G ? (G.cash0 || CASH0) : CASH0, mBase = G ? mB0 + (G.added || 0) : START0; // 내 넣은 돈 (포인트로 추가한 돈 포함)
    const mRet = mEq == null ? null : (mEq / mBase - 1) * 100;
    // 알파 팀 계좌: 내 시작일 다음 날부터 같은 돈으로 (시작 전이면 현금 그대로 대기)
    const C = G && window.Game && Game.alphaClone ? Game.alphaClone(st, G, SC.date, px) : null;
    const aPos = C ? Object.entries(C.pos).map(([sym, p]) => ({ sym, name: so(sym)?.name || p.name || sym, qty: p.qty, avg: p.avg, now: px(sym, p.avg) })) : [];
    const aBase = C ? C.base : mBase, aEq = C ? C.eq : aBase, aCash = C ? C.cash : aBase, aStock = aEq - aCash, aRet = (aEq / aBase - 1) * 100;
    // 경주 그래프 자료 (날짜별 수익률). 지난 날짜의 종목 가격은 종목별 최근 120거래일 종가(closes)에서 읽음
    const days = G ? [...new Set([...(G.eq || []).map(x => x[0]), SC.date])].filter(d => d >= start).sort() : [];
    const mAt = d => { if (!G) return null; let v = null; let b = mB0; for (const [t, e, eb] of (G.eq || [])) if (t <= d) { v = e; b = eb || mB0; } return v == null ? null : (v / b - 1) * 100; };
    const aAt = (d, back) => {
      if (!C) return null;
      const pxd = (sym, fb) => { const s = so(sym), c = s && s.closes; return c && c.length > back ? c[c.length - 1 - back] : px(sym, fb); };
      const c = Game.alphaClone(st, G, d, pxd); return c ? c.ret : null;
    };
    const series = days.map((d, i) => ({ d, a: d === SC.date ? aRet : aAt(d, days.length - 1 - i), m: d === SC.date && mRet != null ? mRet : mAt(d) }));
    // 일별 승부
    let mw = 0, aw = 0;
    for (let i = 1; i < series.length; i++) { const p = series[i - 1], c = series[i]; if (p.m == null || c.m == null || p.a == null || c.a == null) continue; const dm = c.m - p.m, da = c.a - p.a; if (Math.abs(dm - da) < 0.005) continue; dm > da ? mw++ : aw++; }
    return { st, G, start, me: G && { eq: mEq, cash: G.cash, stock: mStock, pnl: mEq - mBase, base: mBase, ret: mRet, pos: mPos },
      ai: { eq: aEq, cash: aCash, stock: aStock, pnl: aEq - aBase, base: aBase, ret: aRet, same: aRet, pos: aPos, trades: C ? C.trades : [] }, series, mw, aw };
  }

  /* 홈 카드용 한 줄 요약 */
  function summary(SC) {
    load(); if (!AI || !SC) return "";
    const S = sides(SC);
    if (!S.me) return `<div class="vs-mini"><span class="sub">대결을 시작하면 다음 거래일부터 알파 팀도 같은 500만 원으로 시작해요</span></div>`;
    const lead = S.me.ret - S.ai.same;
    return `<div class="vs-mini"><span>나 <b class="num ${cls(S.me.ret)}">${pct(S.me.ret)}</b></span><b class="vs-x">VS</b><span>알파 <b class="num ${cls(S.ai.same)}">${pct(S.ai.same)}</b></span></div>
      ${tug(lead)}<p class="sub" style="margin:6px 0 0">${Math.abs(lead) < 0.005 ? "팽팽한 동점" : lead > 0 ? `내가 ${lead.toFixed(2)}%p 앞서요` : `알파가 ${(-lead).toFixed(2)}%p 앞서요`}</p>`;
  }

  /* 줄다리기 막대: 가운데가 동점, 5%p 차이면 끝까지 */
  function tug(lead) {
    const x = Math.max(4, Math.min(96, 50 + lead / 5 * 46));
    return `<div class="vs-tug" role="img" aria-label="${lead >= 0 ? "내가" : "알파가"} ${Math.abs(lead).toFixed(2)}%p 앞섬"><i class="me" style="width:${x}%"></i><i class="ai" style="width:${100 - x}%"></i><b style="left:${x}%"></b></div>`;
  }

  /* 수익률 경주 그래프 */
  function race(series) {
    const pts = series.filter(p => p.a != null);
    if (pts.length < 2) return `<p class="empty">하루 이상 지나면 두 계좌의 수익률 경주 그래프가 그려져요.</p>`;
    const W = 320, H = 150, pl = 6, pr = 78, pt = 10, pb = 22, vals = pts.flatMap(p => [p.a, p.m]).filter(v => v != null);
    let hi = Math.max(0.5, ...vals), lo = Math.min(-0.5, ...vals); const pad = (hi - lo) * 0.12; hi += pad; lo -= pad;
    const X = i => pl + i / (pts.length - 1) * (W - pl - pr), Y = v => pt + (hi - v) / (hi - lo) * (H - pt - pb);
    const path = k => { let d = "", on = false; pts.forEach((p, i) => { if (p[k] == null) { on = false; return; } d += `${on ? "L" : "M"}${X(i).toFixed(1)},${Y(p[k]).toFixed(1)}`; on = true; }); return d; };
    const last = k => { for (let i = pts.length - 1; i >= 0; i--) if (pts[i][k] != null) return [i, pts[i][k]]; return null; };
    const lab = (k, col, name) => { const l = last(k); return l ? `<circle cx="${X(l[0])}" cy="${Y(l[1])}" r="3.5" fill="${col}"/><text x="${X(l[0]) + 6}" y="${Y(l[1]) + 4}" fill="${col}" font-size="11" font-weight="700">${name} ${pct(l[1])}</text>` : ""; };
    return `<svg class="vs-race" viewBox="0 0 ${W} ${H}" role="img" aria-label="날짜별 수익률 경주">
      <line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="#d8dbe6" stroke-dasharray="3 3"/>
      <path d="${path("a")}" fill="none" stroke="#5b8cff" stroke-width="2.4" stroke-linejoin="round"/>
      <path d="${path("m")}" fill="none" stroke="#ff6b8a" stroke-width="2.4" stroke-linejoin="round"/>
      ${lab("a", "#3d6fe6", "알파")}${lab("m", "#e2486b", "나")}
      <text x="${pl}" y="${H - 6}" font-size="10" fill="#8a8fa6">${esc(pts[0].d.slice(5).replace("-", "."))}</text><text x="${W - pr}" y="${H - 6}" font-size="10" fill="#8a8fa6" text-anchor="end">${esc(pts[pts.length - 1].d.slice(5).replace("-", "."))}</text></svg>`;
  }

  const acct = (A, title, who) => !A ? `<div class="vs-acct me"><div class="vs-acct-hd">${who}<b>${title}</b></div><p class="sub">아직 대결을 시작하지 않았어요.</p><a class="cta vs-go" href="#game">500만 원으로 시작</a></div>` :
    `<div class="vs-acct ${title === "알파 팀" ? "ai" : "me"}"><div class="vs-acct-hd">${who}<b>${title}</b></div>
      <div class="vs-eq num">${won(A.eq)}<small>원</small></div><div class="num ${cls(A.ret)} vs-ret">${pct(A.ret)} <small>(${sgn(A.pnl)}원)</small></div>
      <dl class="vs-dl"><dt>현금</dt><dd class="num">${won(A.cash)}</dd><dt>주식</dt><dd class="num">${won(A.stock)}</dd><dt>종목 수</dt><dd class="num">${A.pos.length}개</dd></dl></div>`;

  const holdings = (list, empty) => list.length ? `<ul class="list">${list.map(p => { const r = (p.now / p.avg - 1) * 100, pnl = (p.now - p.avg) * p.qty; return `<li><button class="row" type="button" data-sym="${esc(p.sym)}"><span></span>
      <span style="min-width:0"><div class="nm">${esc(p.name)}</div><div class="meta num">${won(p.qty)}주 · 평단 ${won(p.avg)}</div></span>
      <span class="rt"><div class="px num">${won(p.now * p.qty)}</div><div class="sc num ${cls(r)}">${pct(r)} · ${sgn(pnl)}</div></span></button></li>`; }).join("")}</ul>` : `<p class="empty">${empty}</p>`;

  function view(SC) {
    load();
    const back = `<a class="back" href="#home">‹ 홈</a>`;
    if (!AI || !SC) return `${back}<div class="card"><div class="skel" style="width:50%"></div><div class="skel"></div></div>`;
    const S = sides(SC), T = window.Team;
    const myDir = T ? T.director() : { id: "theo", name: "정서연" }, myStaff = T ? (T.squad ? T.squad() : T.members().slice(0, 3)) : [];
    const rv = T && T.rivals ? T.rivals() : { dir: { id: "seunghyun", name: "백승현" }, staff: [] };
    const lead = S.me ? S.me.ret - S.ai.same : null;
    const verdict = lead == null ? "대결을 시작하면 같은 날부터 수익률을 겨뤄요" : Math.abs(lead) < 0.005 ? "팽팽한 동점이에요" : lead > 0 ? `🏆 내 팀이 <b class="up">${lead.toFixed(2)}%p</b> 앞서요` : `알파 팀이 <b class="down">${(-lead).toFixed(2)}%p</b> 앞서요`;
    const faces = (d, ms) => `<span class="vs-faces"><img class="lead" src="${face(d.id)}" alt="${esc(d.name)}" title="${esc(d.name)} 본부장">${ms.map(m => `<img src="${face(m.id)}" alt="${esc(m.name)}" title="${esc(m.name)}">`).join("")}</span>`;
    const trades = S.ai.trades.slice(-8).reverse();
    const by = r => r.replace(/^THEO/, `${rv.dir.name} 본부장`).replace(/\(규칙\)/, "").trim();

    return `${back}
    <section class="card vs-arena">
      <div class="vs-teams">
        <div class="vs-team me"><div class="k">내 팀</div>${faces(myDir, myStaff)}<div class="sub">${esc(myDir.name)} 본부장 + 직원 ${myStaff.length}명</div></div>
        <div class="vs-x big">VS</div>
        <div class="vs-team ai"><div class="k">${bot(26)} 알파 팀</div>${faces(rv.dir, rv.staff)}<div class="sub">${esc(rv.dir.name)} 본부장 + 직원 ${rv.staff.length}명</div></div>
      </div>
    </section>
    <section class="card">
      <div class="hd"><h2>누가 이기고 있나</h2><span class="sub">${S.start ? esc(S.start.slice(5).replace("-", ".")) + "부터" : ""}${S.me ? ` · 하루 승부 ${S.mw}승 ${S.aw}패` : ""}</span></div>
      ${lead == null ? "" : tug(lead)}<p class="mood">${verdict}</p>
      ${race(S.series)}
      <div class="vs-legend"><span><i style="background:#ff6b8a"></i>나</span><span><i style="background:#5b8cff"></i>알파</span><span class="sub">${S.me ? "같은 기간 수익률" : "알파 수익률"}</span></div>
    </section>
    <section class="card"><div class="hd"><h2>두 계좌</h2><span class="sub">${esc(SC.date)} 종가 기준</span></div>
      <div class="vs-accts">${acct(S.me, "내 팀", `<img class="vs-av" src="${face(myDir.id)}" alt="">`)}${acct(S.ai, "알파 팀", bot(28))}</div>
      ${S.me ? `<button class="cta vs-share" type="button" data-vs="share">결과 이미지로 공유하기</button>` : ""}
    </section>
    ${rankCard(S)}
    <section class="card"><div class="hd"><h2>내 보유 종목</h2><a class="sub" href="#game">거래하기 ›</a></div>${holdings(S.me ? S.me.pos : [], S.me ? "아직 산 종목이 없어요." : "대결을 시작하면 여기에 보여요.")}</section>
    <section class="card"><div class="hd"><h2>알파 보유 종목</h2><span class="sub">현금 ${won(S.ai.cash)}원</span></div>${holdings(S.ai.pos, S.me ? "지금은 현금으로 기다리고 있어요." : "대결을 시작하면 다음 거래일부터 사기 시작해요.")}</section>
    <section class="card"><div class="hd"><h2>알파의 최근 매매</h2><span class="sub">${S.ai.trades.length}회</span></div>
      ${trades.length ? `<ul class="list">${trades.map(t => { const s = window.stockOf ? window.stockOf(t.symbol) : SC.stocks[t.symbol], b = t.side === "BUY"; return `<li><div class="row vs-tr"><span class="${b ? "up" : "down"} vs-side">${b ? "매수" : "매도"}</span>
        <span style="min-width:0"><div class="nm">${esc(s ? s.name : t.symbol)}</div><div class="meta">${esc((t.time || "").slice(5, 10).replace("-", "."))} · ${esc(by(t.reason || ""))}</div></span>
        <span class="rt"><div class="px num">${won(t.qty)}주</div><div class="sc num">@${won(t.price)}</div></span></div></li>`; }).join("")}</ul>` : `<p class="empty">${S.me ? "아직 매매가 없어요. 내 시작일 다음 거래일부터 사고팔아요." : "대결을 시작하면 여기에 보여요."}</p>`}</section>
    <p class="note">알파는 가상 계좌로 움직이는 AI이며, 매매 내역은 참고용이고 투자 권유가 아닙니다. 알파 팀은 내 시작일 다음 거래일부터 나와 같은 돈으로, AI 알파의 매매를 같은 비중으로 따라 해요.</p>`;
  }

  /* ---------- 전체 랭킹 (push.js 가 서버와 통신) ---------- */
  let RB = null, RL = null; // 랭킹 보드 캐시 · 보고 있는 리그
  function rankCard(S) {
    if (!window.Push) return "";
    const sent = S.me && window.Push.rankOn() ? Push.report({ date: window.__SC.date, ret: S.me.ret, ai: S.ai.same, start: S.start, days: S.G.days, done: !!S.G.done }) : Promise.resolve();
    const lg = RL || Push.league();
    if (!RB) sent.then(() => Push.getBoard(lg)).then(b => { RB = b; const el = document.getElementById("vsRank"); if (el) el.outerHTML = rankCard(S); });
    const b = RB, on = window.Push.rankOn(), mon = b && b.season ? +b.season.slice(5) : new Date(Date.now() + 9 * 3600e3).getUTCMonth() + 1;
    const medal = i => (i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : i + 1);
    const rows = b && b.top ? b.top.map((r, i) => `<li class="${r.me ? "me" : ""}"><span class="rk num">${medal(i)}</span><span class="nk">${esc(r.nick)}${r.done ? "" : ' <small class="sub">진행 중</small>'}</span><span class="num ${cls(r.ret)}">${pct(r.ret)}</span></li>`).join("") : "";
    const tabs = ["rookie", "pro"].map(l => `<button type="button" data-lg="${l}" aria-pressed="${l === lg}">${Push.LNAME[l]}${l === Push.league() ? " · 내 리그" : ""}</button>`).join("");
    return `<section class="card" id="vsRank"><div class="hd"><h2>${mon}월 시즌 랭킹</h2><span class="sub">${b && b.total != null ? `${b.total}명 참여` : ""}</span></div>
      <div class="chips vs-lg" role="group" aria-label="리그">${tabs}</div>
      <p class="sub" style="margin:6px 0 8px">매달 1일 새 시즌 · 완주한 게임 3판부터 일반 리그 · 지난 시즌 상위권은 배지와 포인트</p>
      ${!b ? '<p class="sub">불러오는 중…</p>' : b.error ? '<p class="sub">랭킹 서버를 준비 중이에요.</p>' : rows ? `<ol class="vs-rank">${rows}</ol>` : '<p class="empty">아직 참여한 사람이 없어요. 첫 번째가 되어 보세요!</p>'}
      ${b && b.me && b.me.rank > 20 ? `<p class="mood">내 순위 <b>${b.me.rank}위</b> · ${pct(b.me.ret)}</p>` : ""}
      ${on ? "" : `<p class="sub" style="margin-top:8px">${S.me ? "" : "대결을 시작한 뒤 "}<a href="#me">내 정보</a>에서 '랭킹 참여'를 켜면 내 수익률도 올라가요.</p>`}</section>`;
  }
  window.addEventListener("rankchange", () => { RB = null; });
  document.addEventListener("click", e => { const t = e.target.closest("[data-lg]"); if (!t) return; RL = t.dataset.lg; RB = null; window.dispatchEvent(new HashChangeEvent("hashchange")); });

  /* ---------- 결과 공유 이미지 (인스타 세로 1080×1350) ---------- */
  async function share() {
    const SC = window.__SC; if (!SC) return;
    const S = sides(SC); if (!S.me) return;
    const c = document.createElement("canvas"); c.width = 1080; c.height = 1350; const g = c.getContext("2d");
    const F = (w, s) => `${w} ${s}px Pretendard, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif`;
    const bg = g.createLinearGradient(0, 0, 1080, 1350); bg.addColorStop(0, "#f4f2ff"); bg.addColorStop(1, "#eaf4ff"); g.fillStyle = bg; g.fillRect(0, 0, 1080, 1350);
    g.fillStyle = "#6c5ce7"; g.font = F(800, 44); g.textAlign = "center"; g.fillText("AI 투자연구소 · AI 대결", 540, 130);
    g.fillStyle = "#2d2a63"; g.font = F(800, 80); g.fillText("나 VS 알파", 540, 250);
    const lead = S.me.ret - S.ai.same;
    g.font = F(700, 46); g.fillStyle = lead >= 0 ? "#e2486b" : "#3d6fe6"; g.fillText(Math.abs(lead) < 0.005 ? "팽팽한 동점!" : lead > 0 ? `내가 ${lead.toFixed(2)}%p 앞서는 중 🏆` : `알파가 ${(-lead).toFixed(2)}%p 앞서는 중`, 540, 340);
    const box = (x, bgc, name, r, eq) => { g.fillStyle = bgc; g.beginPath(); g.roundRect(x, 420, 440, 400, 40); g.fill();
      g.fillStyle = "#2d2a63"; g.font = F(800, 52); g.fillText(name, x + 220, 510); g.fillStyle = r >= 0 ? "#e2486b" : "#3d6fe6"; g.font = F(800, 96); g.fillText(pct(r), x + 220, 650);
      g.fillStyle = "#6b7088"; g.font = F(600, 38); g.fillText(won(eq) + "원", x + 220, 740); };
    box(80, "#fff1f4", "나", S.me.ret, S.me.eq); box(560, "#eef3ff", "알파", S.ai.same, S.ai.eq);
    g.fillStyle = "#e9e7f5"; g.beginPath(); g.roundRect(120, 900, 840, 40, 20); g.fill();
    const x = Math.max(4, Math.min(96, 50 + lead / 5 * 46)) / 100 * 840;
    g.fillStyle = "#ff8fa6"; g.beginPath(); g.roundRect(120, 900, x, 40, 20); g.fill();
    g.fillStyle = "#2d2a63"; g.beginPath(); g.arc(120 + x, 920, 30, 0, 7); g.fill();
    g.fillStyle = "#6b7088"; g.font = F(600, 36); g.fillText(`${S.start ? S.start.slice(5).replace("-", ".") : ""} ~ ${SC.date.slice(5).replace("-", ".")} · 하루 승부 ${S.mw}승 ${S.aw}패`, 540, 1040);
    g.fillStyle = "#6c5ce7"; g.font = F(700, 38); g.fillText("가상 투자금 모의투자 · 실제 종가 · 수익률(%) 비교", 540, 1160);
    g.fillStyle = "#8a8fa6"; g.font = F(500, 30); g.fillText("juski1004.github.io/ai-trading/app · 참고용, 투자 권유 아님", 540, 1250);
    const blob = await new Promise(r => c.toBlob(r, "image/png"));
    const file = new File([blob], "ai-battle.png", { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) { try { await navigator.share({ files: [file], title: "나 vs 알파 AI 대결" }); return; } catch (e) { if (e.name === "AbortError") return; } }
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "ai-battle.png"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
  document.addEventListener("click", e => { if (e.target.closest('[data-vs="share"]')) share(); });

  const css = document.createElement("style");
  css.textContent = `
  .vs-arena{background:linear-gradient(135deg,#fff3f6,#f4f2ff 50%,#eef5ff)}
  .vs-teams{display:grid;grid-template-columns:1fr auto 1fr;gap:6px;align-items:center}
  .vs-team{text-align:center;min-width:0}.vs-team .k{font-weight:900;font-size:16px;display:flex;align-items:center;justify-content:center;gap:5px;margin-bottom:8px}
  .vs-team.me .k{color:#e2486b}.vs-team.ai .k{color:#3d6fe6}.vs-team .sub{font-size:11.5px;margin-top:6px}
  .vs-faces{display:flex;justify-content:center;flex-wrap:wrap;padding-left:8px}.vs-faces img{width:30px;height:30px;border-radius:50%;object-fit:cover;object-position:50% 15%;border:2px solid #fff;margin:0 0 0 -8px;box-shadow:0 2px 6px rgba(40,50,90,.12)}
  .vs-faces img.lead{width:40px;height:40px;margin-top:-5px}
  .vs-x{font-weight:900;color:#6c5ce7}.vs-x.big{font-size:22px}
  .vs-story{text-align:center;margin:12px 0 0;line-height:1.5}
  .vs-bot{position:relative;display:inline-block;border-radius:50%;overflow:hidden;flex:none;vertical-align:middle}.vs-bot svg,.vs-bot img{position:absolute;inset:0;width:100%;height:100%}.vs-bot img{object-fit:cover;object-position:50% 15%;z-index:1}
  .vs-tug{position:relative;display:flex;height:14px;border-radius:10px;overflow:visible;margin:14px 6px 4px}
  .vs-tug i{display:block;height:100%}.vs-tug i.me{background:linear-gradient(90deg,#ffc2cf,#ff8fa6);border-radius:10px 0 0 10px}.vs-tug i.ai{background:linear-gradient(90deg,#a9c4ff,#d3e1ff);border-radius:0 10px 10px 0}
  .vs-tug b{position:absolute;top:50%;width:24px;height:24px;margin:-12px 0 0 -12px;border-radius:50%;background:#2d2a63;border:3px solid #fff;box-shadow:0 3px 8px rgba(40,50,90,.25);transition:left .6s}
  .vs-race{width:100%;height:auto;margin-top:10px}
  .vs-legend{display:flex;gap:14px;align-items:center;font-size:12.5px;margin-top:4px}.vs-legend i{display:inline-block;width:14px;height:4px;border-radius:2px;margin-right:5px;vertical-align:middle}
  .vs-accts{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
  .vs-acct{border-radius:16px;padding:12px;min-width:0}.vs-acct.me{background:#fff1f4}.vs-acct.ai{background:#eef3ff}
  .vs-acct-hd{display:flex;align-items:center;gap:6px;font-size:14px}.vs-av{width:28px;height:28px;border-radius:50%;object-fit:cover;object-position:50% 15%}
  .vs-eq{font-size:19px;font-weight:800;margin-top:8px}.vs-eq small{font-size:12px;margin-left:2px;color:var(--muted)}.vs-ret{font-size:14px;font-weight:700}.vs-ret small{font-weight:500}
  .vs-dl{display:grid;grid-template-columns:auto 1fr;gap:2px 8px;margin:8px 0 0;font-size:12.5px}.vs-dl dt{color:var(--muted)}.vs-dl dd{margin:0;text-align:right}
  .vs-go{display:block;text-align:center;text-decoration:none;font-size:14px;padding:10px;margin-top:10px}
  .vs-share{margin-top:12px}
  .vs-tr{cursor:default;grid-template-columns:34px minmax(0,1fr) auto}.vs-side{font-size:12.5px;font-weight:700;text-align:center}
.vs-lg{margin-top:4px}.vs-lg button{font-size:12.5px}
.vs-rank{list-style:none;margin:6px 0 0;padding:0}.vs-rank li{display:grid;grid-template-columns:30px 1fr auto;gap:8px;align-items:center;padding:9px 4px;border-top:1px solid var(--line,#eceef6);font-size:14.5px}
  .vs-rank li:first-child{border-top:0}.vs-rank li.me{background:#f4f2ff;border-radius:12px}.vs-rank .rk{font-weight:800;color:#6c5ce7;text-align:center}.vs-rank .nk{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .vs-mini{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px;font-size:14px}.vs-mini b.num{font-size:18px;margin-left:4px}
  a.cta{display:block;text-align:center;text-decoration:none}`;
  document.head.appendChild(css);

  window.Versus = { view, summary };
})();
