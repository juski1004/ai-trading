/* 모의투자 게임 (앱 '투자게임' 탭).
   - 가상 1,000만 원, 기간 1주~3개월, 실제 종가(data/scores.json)로 사고팔기
   - 날짜가 바뀐 데이터를 처음 볼 때 자동 손절(-5%)·익절(+10%) 처리 (그날 종가 체결)
   - 상대: AI 투자자 '알파'의 계좌(data/ai.json)의 같은 기간 수익률, 코스피 같은 기간 등락
   - 주문 체결 시점: 화면 데이터가 오늘(KST) 장 마감 종가면 바로 체결, 아니면(장중·주말) '예약 주문'으로 두었다가
     다음 장 마감 데이터가 들어올 때 그날 종가로 체결한다 (어제 가격으로 오늘 사는 일이 없게)
   - 기록은 이 휴대폰에만 저장(localStorage). 서버로 보내지 않음.
   index.html 이 Game.view(SC, sym) 를 부르고, 화면 안의 버튼은 여기서 직접 처리한다. */
(() => {
  const KEY = "aiLab.game.v1", HIST = "aiLab.games.v1";
  const R = { cash0: 10_000_000, fee: 0.00015, tax: 0.0018, stop: -5, take: 10 };
  const PERIODS = [["1주", 7], ["2주", 14], ["1개월", 30], ["2개월", 60], ["3개월", 90]];
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => { const t = Math.abs(x) < 0.005 ? "0.00" : x.toFixed(2); return (x >= 0.005 ? "+" : "") + t + "%"; };
  const cls = x => (x >= 0.005 ? "up" : x <= -0.005 ? "down" : "flat");
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const addDays = (d, n) => { const x = new Date(d + "T00:00:00"); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };
  const daysBetween = (a, b) => Math.round((new Date(b + "T00:00:00") - new Date(a + "T00:00:00")) / 864e5);
  const todayKST = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const live = () => !!SC && SC.date === todayKST(); // 오늘 종가 데이터가 들어와 있으면 바로 체결 가능

  const load = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* 저장이 막힌 브라우저: 이번 접속 동안만 유지 */ } };

  let SC = null, AI = null, G = load(KEY, null), side = "B", pickPeriod = 30, msg = "";
  fetch("../data/ai.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => { AI = d; redraw(); }).catch(() => {});

  /* ---------- 계산 ---------- */
  const stockOf = sym => (SC && SC.stocks[sym]) || (window.__PX && window.__PX.stocks && window.__PX.stocks[sym]) || null; // 분석 종목 → 거래 전용 시세
  const priceOf = sym => { const s = stockOf(sym); return s ? s.price : null; };
  const equity = g => g.cash + Object.entries(g.pos).reduce((s, [sym, p]) => s + p.qty * (priceOf(sym) ?? p.last), 0);
  const ret = g => (equity(g) / R.cash0 - 1) * 100;
  const kospiRet = g => (SC && SC.market && SC.market.kospi && g.kospi0 ? (SC.market.kospi.v / g.kospi0 - 1) * 100 : null);
  let kFetch = false;
  function fillKospi(g) { // 시작일 코스피가 비어 있으면 시세 자료에서 찾아 채움
    if (!g || g.kospi0 || kFetch) return; kFetch = true;
    fetch("../data/market.json", { cache: "force-cache" }).then(r => (r.ok ? r.json() : null)).then(m => {
      if (!m || !m.dates || !m.macro || !m.macro.kospi) return;
      const i = m.dates.findIndex(d => d >= g.start); if (i < 0) return;
      g.kospi0 = m.macro.kospi[i]; save(KEY, g); redraw();
    }).catch(() => {});
  }
  function aiRet(g) {
    const h = AI && AI.state && AI.state.equity_history;
    if (!h || !h.length) return null;
    const at = d => { let v = null; for (const [t, e] of h) if (t.slice(0, 10) <= d) v = e; return v; };
    const base = at(g.start) ?? R.cash0, now = at(g.lastDate) ?? h[h.length - 1][1];
    return (now / base - 1) * 100;
  }

  // 실제 시장처럼: 거래 정지 종목은 체결 안 됨, 상한가(+29.5% 이상)에 매수·하한가에 매도는 체결 안 됨
  function blocked(s, sell) {
    if (!s) return "시세가 없는 종목이에요.";
    if (s.halt || s.vol_ratio === 0) return `${s.name}은(는) 거래 정지 상태라 체결되지 않았어요.`;
    if (!sell && s.chg >= 29.5) return `${s.name}은(는) 상한가라 살 수 없어요 (파는 사람이 없어요).`;
    if (sell && s.chg <= -29.5) return `${s.name}은(는) 하한가라 팔 수 없어요 (사는 사람이 없어요).`;
    return "";
  }
  function trade(g, sym, qty, sell, why) {
    const s = stockOf(sym), bad = blocked(s, sell); if (bad) return (why !== "직접 주문" ? why + ": " : "") + bad;
    const p = s.price;
    if (sell) {
      const pos = g.pos[sym]; if (!pos) return "보유하지 않은 종목이에요.";
      if (qty <= 0) return "수량을 확인해 주세요.";
      if (qty > pos.qty) return `보유 수량(${won(pos.qty)}주)보다 많이 팔 수 없어요.`;
      const cost = pos.cost * qty / pos.qty, cash = p * qty * (1 - R.fee - R.tax), pnl = cash - cost;
      g.cash += cash; pos.qty -= qty; pos.cost -= cost; if (!pos.qty) delete g.pos[sym];
      g.trades.push({ d: SC.date, sym, name: s.name, side: "S", qty, p, pnl: Math.round(pnl), why });
      return `${why !== "직접 주문" ? why + ": " : ""}${s.name} ${won(qty)}주 매도 (${won(p)}원) · 손익 ${pnl >= 0 ? "+" : ""}${won(pnl)}원`;
    }
    const maxQ = Math.floor(g.cash / (p * (1 + R.fee)));
    if (qty <= 0) return "수량을 확인해 주세요.";
    if (qty > maxQ) return `현금이 부족해요. 최대 ${won(maxQ)}주까지 살 수 있어요.`;
    const cost = p * qty * (1 + R.fee); g.cash -= cost;
    const pos = g.pos[sym] || { qty: 0, cost: 0, avg: 0, name: s.name };
    pos.avg = (pos.avg * pos.qty + p * qty) / (pos.qty + qty); pos.qty += qty; pos.cost += cost; pos.last = p; g.pos[sym] = pos;
    g.trades.push({ d: SC.date, sym, name: s.name, side: "B", qty, p, why });
    return `${why !== "직접 주문" ? why + ": " : ""}${s.name} ${won(qty)}주 매수 (${won(p)}원) · ${won(cost)}원`;
  }

  /* 새 거래일 데이터를 처음 볼 때: 자동 손절·익절, 자산 기록, 기간 종료 확인 */
  function catchUp(g) {
    if (!SC || g.done || SC.date <= g.lastDate) return;
    const notes = [];
    // 예약 주문: 새로 들어온 날의 종가로 체결 (돈·수량이 모자라면 가능한 만큼만)
    for (const o of g.orders || []) {
      const s = stockOf(o.sym); if (!s) { notes.push(`${o.name} 예약 주문 취소 (시세 없음)`); continue; }
      let q = o.qty;
      if (o.side === "S") q = Math.min(q, g.pos[o.sym] ? g.pos[o.sym].qty : 0);
      else q = Math.min(q, Math.floor(g.cash / (s.price * (1 + R.fee))));
      notes.push(q > 0 ? trade(g, o.sym, q, o.side === "S", "예약 주문 체결") : `${o.name} 예약 주문 취소 (${o.side === "S" ? "보유 수량" : "현금"} 부족)`);
    }
    g.orders = [];
    if (g.autoExit) for (const [sym, p] of Object.entries(g.pos)) {
      const now = priceOf(sym); if (now == null) continue;
      const chg = (now / p.avg - 1) * 100;
      if (chg <= R.stop) notes.push(trade(g, sym, p.qty, true, `자동 손절 (${chg.toFixed(1)}%)`));
      else if (chg >= R.take) notes.push(trade(g, sym, p.qty, true, `자동 익절 (+${chg.toFixed(1)}%)`));
    }
    for (const [sym, p] of Object.entries(g.pos)) { const v = priceOf(sym); if (v != null) p.last = v; }
    g.lastDate = SC.date;
    g.eq.push([SC.date, Math.round(equity(g))]);
    if (SC.date >= g.end) finish(g);
    if (notes.length) g.note = { d: SC.date, t: notes.join(" · ") }; // 새 거래일 처리 결과는 그날 동안 화면에 남김
    save(KEY, g);
  }
  function finish(g) {
    g.done = true;
    const sells = g.trades.filter(t => t.side === "S");
    const rec = { start: g.start, end: g.lastDate, days: g.days, ret: ret(g), ai: aiRet(g), kospi: kospiRet(g),
      trades: g.trades.length, win: sells.length ? sells.filter(t => t.pnl > 0).length / sells.length * 100 : null };
    const hist = load(HIST, []); hist.unshift(rec); save(HIST, hist.slice(0, 20));
    g.result = rec;
    window.dispatchEvent(new CustomEvent("aiLab:gameEnd", { detail: rec }));
  }

  /* ---------- 화면 ---------- */
  function alphaLine() { // 시작 화면: 알파 팀의 지금 성적 (겨룰 상대가 누군지)
    const st = AI && AI.state, eh = (st && st.equity_history) || []; if (eh.length < 2) return "";
    const r = (eh[eh.length - 1][1] / eh[0][1] - 1) * 100, d = Math.max(1, Math.round((new Date(eh[eh.length - 1][0]) - new Date(eh[0][0])) / 864e5));
    return `<p class="g-alpha">상대 '알파' 팀은 지금 <b class="${cls(r)}">${pct(r)}</b> (${d}일째) · 이기면 연구소 포인트 +100P</p>`;
  }
  function setupView() {
    const hist = load(HIST, []);
    return `<section class="card">
      <h2>하루 5분, 퇴근길 종가 스윙 게임</h2>
      <p class="sub"><b>바쁜 직장인을 위한 스윙 매매</b>예요. 가상 1,000만 원으로 <b>실제 거래소 종가</b>를 따라 투자하고, 같은 기간 AI 팀 '알파'·코스피와 수익률을 겨뤄요. 저녁 6시 브리핑 듣고 주문만 넣으면 끝 — 며칠~몇 주 들고 가는 스윙이라 하루 한 번이면 충분하고, 장중 등락에 휘둘리지 않아요.</p>
      ${alphaLine()}
      <div class="g-k">투자 기간</div>
      <div class="chips" role="group" aria-label="투자 기간">${PERIODS.map(([t, d]) => `<button type="button" data-g="period" data-v="${d}" aria-pressed="${d === pickPeriod}">${t}</button>`).join("")}</div>
      <ul class="g-rules">
        <li>매일 장 마감 가격(실제 종가)으로 사고팔아요. 장중에 낸 주문은 그날 종가, 장 마감 뒤 주문은 다음 거래일 종가로 체결돼요. 수수료 0.015%, 팔 때 세금 0.18%를 반영해요.</li>
        <li>자동 손절 −5% · 익절 +10%를 켜 둘 수 있어요.</li>
        <li>기록은 이 휴대폰에만 저장돼요. 주문마다 +5P, 완주하면 +50P.</li>
      </ul>
      <button class="cta" type="button" data-g="start">1,000만 원으로 시작하기</button>
    </section>
    ${hist.length ? `<section class="card"><div class="hd"><h2>지난 게임</h2></div><ul class="list">${hist.map(h => `<li><div class="row g-hrow"><span></span>
      <span><div class="nm">${esc(h.start.slice(5))} ~ ${esc(h.end.slice(5))} · ${h.days}일</div><div class="meta">AI ${h.ai == null ? "-" : pct(h.ai)} · 코스피 ${h.kospi == null ? "-" : pct(h.kospi)}</div></span>
      <span class="rt"><div class="px num ${cls(h.ret)}">${pct(h.ret)}</div><div class="sc">${h.ai == null ? "" : h.ret > h.ai ? "AI에 승리" : h.ret < h.ai ? "AI에 패배" : "무승부"}</div></span></div></li>`).join("")}</ul></section>` : ""}`;
  }

  function scoreboard(g) {
    const me = ret(g), ai = aiRet(g), kp = kospiRet(g);
    const box = (k, v, c) => `<div class="mk"><div class="k">${k}</div><div class="v num ${v == null ? "flat" : cls(v)}">${v == null ? "-" : pct(v)}</div>${c ? `<div class="c sub">${c}</div>` : ""}</div>`;
    const lead = ai == null ? "" : Math.abs(me - ai) < 0.005 ? "AI와 동률이에요" : me > ai ? `AI보다 <b class="up">${(me - ai).toFixed(2)}%p</b> 앞서요` : `AI보다 <b class="down">${(ai - me).toFixed(2)}%p</b> 뒤져요`;
    return `<div class="mkt">${box("나", me, "")}${box("알파", ai, "AI 투자자")}${box("코스피", kp, "")}</div>${lead ? `<p class="mood">${lead}</p>` : ""}`;
  }
  /* 진행 중 화면용 한 줄 (자세한 비교는 AI 대결 화면에) */
  function scoreline(g) {
    const me = ret(g), ai = aiRet(g), kp = kospiRet(g);
    const lead = ai == null ? "" : Math.abs(me - ai) < 0.005 ? "알파와 동점" : me > ai ? `알파보다 <b class="up">${(me - ai).toFixed(2)}%p</b> 앞서요` : `알파보다 <b class="down">${(ai - me).toFixed(2)}%p</b> 뒤져요`;
    return `<a class="g-line" href="#vs"><span>${lead || "알파와 비교 준비 중"}</span><span class="sub">알파 ${ai == null ? "-" : pct(ai)} · 코스피 ${kp == null ? "-" : pct(kp)} · 자세히 ›</span></a>`;
  }

  function gameView(g) {
    const eq = equity(g), left = Math.max(0, daysBetween(SC.date, g.end)), passed = Math.min(g.days, daysBetween(g.start, SC.date));
    const pos = Object.entries(g.pos);
    if (g.done) {
      const r = g.result || {};
      const verdict = r.ai == null ? "" : r.ret > r.ai ? "🏆 알파를 이겼어요!" : r.ret < r.ai ? "알파가 이겼어요. 다음엔 꼭!" : "알파와 비겼어요.";
      return `<section class="card g-end"><div class="ic" aria-hidden="true">🏁</div><h2>게임 끝 · 성적표</h2><p class="sub">${esc(g.start)} ~ ${esc(g.lastDate)} (${g.days}일)</p>
        <div class="g-big num ${cls(r.ret)}">${pct(r.ret)}</div><p class="mood">${verdict}</p>${scoreboard(g)}
        <div class="tiles"><div class="tile"><div class="k">최종 자산</div><div class="v num">${won(eq)}원</div></div>
        <div class="tile"><div class="k">거래 / 승률</div><div class="v num">${r.trades}회 · ${r.win == null ? "-" : Math.round(r.win) + "%"}</div></div></div>
        <button class="cta" type="button" data-g="new">새 게임 시작</button></section>${reviewView(g)}${tradesView(g)}`;
    }
    return `<section class="card">
      <div class="hd"><h2>내 게임 계좌</h2><span class="sub">D-${left} · ${esc(g.end.slice(5).replace("-", "."))} 종료</span></div>
      <div class="g-big num">${won(eq)}<small>원</small></div>
      <div class="g-prog"><i style="width:${Math.min(100, passed / g.days * 100)}%"></i></div>
      <p class="sub">${g.days}일 중 ${passed}일 지남 · 현금 ${won(g.cash)}원 · ${pct(ret(g))}</p>
      ${scoreline(g)}
      ${g.note && g.note.d === SC.date ? `<p class="g-msg" role="status">${esc(g.note.t)}</p>` : ""}
      ${msg ? `<p class="g-msg" role="status">${esc(msg)}</p>` : ""}
    </section>
    ${(g.orders || []).length ? `<section class="card"><div class="hd"><h2>예약 주문</h2><span class="sub">다음 장 마감 종가로 체결</span></div><ul class="list">${g.orders.map((o, i) => `<li><div class="row g-hrow"><span class="${o.side === "B" ? "up" : "down"} g-side">${o.side === "B" ? "매수" : "매도"}</span>
        <span style="min-width:0"><div class="nm">${esc(o.name)}</div><div class="meta">${won(o.qty)}주 · ${esc(o.at.slice(5))} 주문</div></span><span class="rt"><button class="g-cancel" type="button" data-g="cancel" data-v="${i}">취소</button></span></div></li>`).join("")}</ul></section>` : ""}
    <section class="card"><div class="hd"><h2>보유 종목</h2><a class="sub" href="#analysis">+ 종목 사기</a></div>
      ${pos.length ? `<ul class="list">${pos.map(([sym, p]) => { const now = priceOf(sym) ?? p.last, r = (now / p.avg - 1) * 100; return `<li><button class="row" type="button" data-g="open" data-v="${esc(sym)}">
        <span></span><span style="min-width:0"><div class="nm">${esc(p.name)}</div><div class="meta num">${won(p.qty)}주 · 평단 ${won(p.avg)}</div></span>
        <span class="rt"><div class="px num">${won(now * p.qty)}</div><div class="sc num ${cls(r)}">${pct(r)}</div></span></button></li>`; }).join("")}</ul>`
        : `<p class="empty">아직 산 종목이 없어요. <a href="#analysis">분석 탭</a>에서 종목을 골라 "모의투자 해 보기"를 눌러 보세요.</p>`}
      <label class="g-auto"><input type="checkbox" data-g="auto" ${g.autoExit ? "checked" : ""}> 자동 손절 −5% · 익절 +10%</label>
    </section>
    ${tradesView(g)}
    <button class="g-quit" type="button" data-g="quit">게임 그만두기</button>`;
  }

  /* 게임 끝난 뒤 복기: 잘한 것·아쉬운 것을 본부장이 정리 */
  function review(g) {
    const r = g.result || {}, sells = g.trades.filter(t => t.side === "S" && t.pnl != null), buys = g.trades.filter(t => t.side === "B");
    const best = sells.length ? sells.reduce((a, b) => (b.pnl > a.pnl ? b : a)) : null, worst = sells.length ? sells.reduce((a, b) => (b.pnl < a.pnl ? b : a)) : null;
    const auto = g.trades.filter(t => /자동/.test(t.why || "")).length;
    const held = Object.values(g.pos).length, lines = [];
    if (r.ai != null) lines.push(r.ret > r.ai ? `알파보다 ${(r.ret - r.ai).toFixed(2)}%p 앞서며 이겼어요.` : r.ret < r.ai ? `알파에 ${(r.ai - r.ret).toFixed(2)}%p 뒤졌어요.` : "알파와 비겼어요.");
    if (r.kospi != null) lines.push(r.ret > r.kospi ? `같은 기간 코스피(${pct(r.kospi)})보다 잘했어요.` : `같은 기간 코스피(${pct(r.kospi)})를 못 따라갔어요.`);
    if (!g.trades.length) lines.push("한 번도 거래하지 않았어요. 다음엔 한 종목이라도 계획대로 사 보세요.");
    else {
      lines.push(`거래 ${g.trades.length}회 중 매도 ${sells.length}회, 승률 ${r.win == null ? "-" : Math.round(r.win) + "%"}.${auto ? ` 자동 손절·익절이 ${auto}번 지켜 줬어요.` : ""}`);
      if (best) lines.push(`가장 잘한 매매: ${best.name} ${won(best.qty)}주 (+${won(best.pnl)}원).`);
      if (worst && worst.pnl < 0) lines.push(`가장 아쉬운 매매: ${worst.name} ${won(worst.qty)}주 (${won(worst.pnl)}원). ${worst.why && /손절/.test(worst.why) ? "손절 원칙은 잘 지켰어요." : "손절선을 미리 정해 두면 손실을 줄일 수 있어요."}`);
      if (buys.length >= 6) lines.push("매수가 잦았어요. 종목 수를 줄이고 분할로 들어가는 편이 수수료와 실수를 줄여요.");
      if (held) lines.push(`끝날 때 ${held}종목을 들고 있었어요. 기간 안에 정리하는 계획도 세워 보세요.`);
    }
    return lines;
  }
  function reviewView(g) {
    const d = window.Team ? Team.director() : { id: "theo", name: "정서연" }, lines = review(g);
    return `<section class="card"><div class="hd"><h2>본부장 복기</h2><span class="sub">${esc(d.name)} 본부장</span></div>
      <ul class="g-review">${lines.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
      <button class="cta" type="button" data-g="share">성적표 이미지로 공유하기</button></section>`;
  }
  async function shareResult(g) {
    const r = g.result || {}, c = document.createElement("canvas"); c.width = 1080; c.height = 1350; const x = c.getContext("2d");
    const F = (w, s) => `${w} ${s}px Pretendard, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif`;
    const bg = x.createLinearGradient(0, 0, 1080, 1350); bg.addColorStop(0, "#f4f2ff"); bg.addColorStop(1, "#fff1f4"); x.fillStyle = bg; x.fillRect(0, 0, 1080, 1350);
    x.textAlign = "center"; x.fillStyle = "#6c5ce7"; x.font = F(800, 44); x.fillText("AI 투자연구소 · 모의투자 성적표", 540, 130);
    x.fillStyle = "#2d2a63"; x.font = F(700, 40); x.fillText(`${g.start} ~ ${g.lastDate} (${g.days}일)`, 540, 210);
    x.fillStyle = r.ret >= 0 ? "#e2486b" : "#3d6fe6"; x.font = F(800, 150); x.fillText(pct(r.ret), 540, 420);
    x.fillStyle = "#2d2a63"; x.font = F(700, 48); x.fillText(r.ai == null ? "" : r.ret > r.ai ? "🏆 알파를 이겼어요" : r.ret < r.ai ? "알파가 이겼어요" : "알파와 비겼어요", 540, 510);
    const box = (bx, name, v, bgc) => { x.fillStyle = bgc; x.beginPath(); x.roundRect(bx, 580, 300, 190, 32); x.fill(); x.fillStyle = "#2d2a63"; x.font = F(700, 36); x.fillText(name, bx + 150, 640); x.fillStyle = v == null ? "#8a8fa6" : v >= 0 ? "#e2486b" : "#3d6fe6"; x.font = F(800, 58); x.fillText(v == null ? "-" : pct(v), bx + 150, 725); };
    box(60, "나", r.ret, "#fff1f4"); box(390, "알파", r.ai, "#eef3ff"); box(720, "코스피", r.kospi, "#f1f3f8");
    x.fillStyle = "#2d2a63"; x.font = F(600, 36); x.textAlign = "left"; review(g).slice(0, 4).forEach((l, i) => x.fillText("· " + (l.length > 34 ? l.slice(0, 33) + "…" : l), 80, 880 + i * 62));
    x.textAlign = "center"; x.fillStyle = "#6c5ce7"; x.font = F(700, 36); x.fillText("가상 1,000만 원 · 실제 종가 기준 · 참고용", 540, 1200);
    x.fillStyle = "#8a8fa6"; x.font = F(500, 30); x.fillText("juski1004.github.io/ai-trading/app", 540, 1260);
    const blob = await new Promise(res => c.toBlob(res, "image/png")), file = new File([blob], "ai-report.png", { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) { try { await navigator.share({ files: [file], title: "모의투자 성적표" }); return; } catch (e) { if (e.name === "AbortError") return; } }
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "ai-report.png"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
  function tradesView(g) {
    const t = g.trades.slice(-15).reverse();
    return `<section class="card"><div class="hd"><h2>거래 내역</h2><span class="sub">${g.trades.length}회</span></div>
      ${t.length ? `<ul class="list">${t.map(x => `<li><div class="row g-hrow"><span class="${x.side === "B" ? "up" : "down"} g-side">${x.side === "B" ? "매수" : "매도"}</span>
        <span style="min-width:0"><div class="nm">${esc(x.name)}</div><div class="meta">${esc(x.d.slice(5))} · ${esc(x.why || "")}</div></span>
        <span class="rt"><div class="px num">${won(x.qty)}주</div><div class="sc num">${x.pnl != null ? `<span class="${cls(x.pnl)}">${x.pnl >= 0 ? "+" : ""}${won(x.pnl)}원</span>` : "@" + won(x.p)}</div></span></div></li>`).join("")}</ul>` : '<p class="empty">아직 거래가 없어요.</p>'}</section>`;
  }

  function orderView(g, sym) {
    const s = stockOf(sym);
    if (!s) return `<a class="back" href="#game">‹ 내 계좌</a><div class="card"><h2>지금은 거래할 수 없는 종목이에요</h2><p class="sub">시가총액 상위 종목만 모의투자할 수 있어요.</p></div>`;
    const bad = blocked(s, side === "S");
    const held = g.pos[sym], maxB = Math.floor(g.cash / (s.price * (1 + R.fee))), maxS = held ? held.qty : 0, B = side === "B";
    const maxQ = B ? maxB : maxS;
    return `<a class="back" href="#game">‹ 내 계좌</a>
    <section class="card">
      <div class="dhead"><div><div class="dname">${esc(s.name)}</div><div class="meta">${esc(s.code)} · ${s.score == null ? "AI 분석 없음 (거래만 가능)" : `AI 점수 ${Math.round((s.score + 1) * 50)}점 · <span class="chip ${s.label}">${s.label}</span>`}</div></div>
        <div><div class="dprice num">${won(s.price)}</div><div class="meta num ${cls(s.chg)}" style="text-align:right">${pct(s.chg)}</div></div></div>
      <p class="sub">${live() ? `${esc(SC.date)} 종가로 바로 체결돼요` : `지금은 장 마감 전이라 <b>다음 장 마감 종가</b>로 체결돼요 (예약 주문)`}${s.target ? ` · 참고 목표가 ${won(s.target)} · 손절가 ${won(s.stop)}` : ""}</p>
      ${bad ? `<p class="g-msg down" role="status">${esc(bad)}</p>` : ""}
      ${held ? `<p class="mood">보유 ${won(held.qty)}주 · 평단 ${won(held.avg)} · <span class="${cls(s.price / held.avg - 1)}">${pct((s.price / held.avg - 1) * 100)}</span></p>` : ""}
      <div class="g-side2" role="group" aria-label="주문 종류"><button type="button" data-g="side" data-v="B" aria-pressed="${B}" class="b">사기</button><button type="button" data-g="side" data-v="S" aria-pressed="${!B}" class="s">팔기</button></div>
      <label class="g-k" for="gq">수량 (최대 ${won(maxQ)}주)</label>
      <div class="g-qty"><input id="gq" type="number" inputmode="numeric" min="0" max="${maxQ}" step="1" value="0"><span>주</span></div>
      <div class="chips">${[["10%", 0.1], ["25%", 0.25], ["50%", 0.5], ["최대", 1]].map(([t, f]) => `<button type="button" data-g="frac" data-v="${f}" data-max="${maxQ}">${t}</button>`).join("")}</div>
      <p class="sub" id="gamt">주문 금액 0원 · 현금 ${won(g.cash)}원</p>
      <button class="cta ${B ? "g-buy" : "g-sell"}" type="button" data-g="order" data-v="${esc(sym)}" ${maxQ && !bad ? "" : "disabled"}>${live() ? (B ? "사기" : "팔기") : (B ? "장 마감 종가로 사기 (예약)" : "장 마감 종가로 팔기 (예약)")}</button>
      ${msg ? `<p class="g-msg" role="status">${esc(msg)}</p>` : ""}
    </section>
    ${s.score == null ? "" : `<a class="back" href="#analysis/${encodeURIComponent(sym)}">이 종목 AI 분석 보기 ›</a>`}`;
  }

  function view(sc, sym) {
    SC = sc;
    if (!SC) return `<div class="card"><div class="skel"></div><div class="skel" style="width:60%"></div></div>`;
    if (G) { catchUp(G); fillKospi(G); }
    const body = !G ? (sym ? `<div class="card"><h2>먼저 게임을 시작해 주세요</h2><p class="sub">기간을 고르고 시작하면 바로 이 종목을 살 수 있어요.</p></div>` : "") + setupView()
      : sym && !G.done ? orderView(G, sym) : gameView(G);
    const out = `<div id="gameRoot">${sym && G && !G.done ? "" : '<div class="g-top"><a class="back" href="#home">‹ 홈</a><a class="back" href="#vs">AI 대결 보기 ›</a></div>'}${body}<p class="note">모의투자는 가상 돈으로 하는 연습이며 실제 거래가 아닙니다. 하루 한 번 장 마감 가격으로 체결되고, 실제 수익을 보장하지 않습니다.</p></div>`;
    msg = "";
    return out;
  }

  function redraw() {
    const root = document.getElementById("gameRoot");
    if (!root || !SC) return;
    const [, arg] = location.hash.slice(1).split("/");
    root.outerHTML = view(SC, arg && decodeURIComponent(arg));
  }

  /* ---------- 버튼 ---------- */
  document.addEventListener("click", e => {
    const b = e.target.closest("#gameRoot [data-g]"); if (!b || b.type === "checkbox") return;
    e.stopPropagation();
    const a = b.dataset.g, v = b.dataset.v;
    if (a === "period") pickPeriod = +v;
    else if (a === "new") { G = null; save(KEY, null); }  // 끝난 게임 → 기간 고르는 화면으로
    else if (a === "start") {
      G = { start: SC.date, end: addDays(SC.date, pickPeriod), days: pickPeriod, lastDate: SC.date, cash: R.cash0, pos: {}, trades: [],
        eq: [[SC.date, R.cash0]], kospi0: SC.market && SC.market.kospi ? SC.market.kospi.v : null, autoExit: true, done: false };
      save(KEY, G);
    } else if (a === "quit") {
      if (!confirm("게임을 그만둘까요? 지금 결과가 성적표로 남아요.")) return;
      finish(G); save(KEY, G);
    } else if (a === "side") side = v;
    else if (a === "frac") { const q = document.getElementById("gq"); q.value = Math.floor(+b.dataset.max * +v); q.dispatchEvent(new Event("input", { bubbles: true })); return; }
    else if (a === "open") { location.hash = "game/" + encodeURIComponent(v); return; }
    else if (a === "order") {
      const q = Math.floor(+document.getElementById("gq").value || 0), s = stockOf(v);
      if (q > 0) window.dispatchEvent(new CustomEvent("aiLab:trade"));
      if (live() || q <= 0) msg = trade(G, v, q, side === "S", "직접 주문");
      else { (G.orders = G.orders || []).push({ sym: v, name: s.name, qty: q, side, at: todayKST() }); msg = `${s.name} ${won(q)}주 ${side === "S" ? "매도" : "매수"} 예약 완료 · 다음 장 마감 종가로 체결돼요`; }
      save(KEY, G);
    }
    else if (a === "cancel") { (G.orders || []).splice(+v, 1); save(KEY, G); }
    else if (a === "share") { shareResult(G); return; }
    redraw();
  }, true);
  document.addEventListener("change", e => {
    if (e.target.matches('#gameRoot [data-g="auto"]')) { G.autoExit = e.target.checked; save(KEY, G); }
  });
  document.addEventListener("input", e => {
    if (e.target.id !== "gq" || !SC) return;
    const [, arg] = location.hash.slice(1).split("/"), s = stockOf(decodeURIComponent(arg || ""));
    const el = document.getElementById("gamt"); if (!s || !el) return;
    const q = Math.max(0, Math.floor(+e.target.value || 0));
    el.textContent = `주문 금액 ${won(q * s.price)}원 · 현금 ${won(G.cash)}원`;
  });

  /* 이 파일 전용 모양 */
  const css = document.createElement("style");
  css.textContent = `
  .g-top{display:flex;justify-content:space-between}
  .g-k{font-size:13px;color:var(--muted);margin:14px 0 6px;display:block}
  .g-alpha{margin:10px 0 0;padding:10px 14px;border-radius:14px;background:var(--lav-s,#efedff);font-size:14px}
  .g-rules{margin:14px 0 0;padding-left:18px;font-size:13.5px;color:var(--muted);display:flex;flex-direction:column;gap:3px}
  .g-big{font-family:var(--f-disp,inherit);font-size:34px;font-weight:600;letter-spacing:-.5px;margin-top:4px}.g-big small{font-size:16px;margin-left:3px;color:var(--muted)}
  .g-prog{height:6px;border-radius:6px;background:var(--soft);margin:8px 0 4px;overflow:hidden}.g-prog i{display:block;height:100%;background:var(--gold-g,var(--brand2));}
  .g-msg{margin:12px 0 0;padding:10px 13px;border-radius:14px;background:var(--lav-s,#efedff);border:1px solid var(--line2,var(--line));font-size:14px}
  .g-auto{display:flex;gap:8px;align-items:center;font-size:13.5px;color:var(--muted);margin-top:10px}
  .g-hrow{cursor:default;grid-template-columns:34px minmax(0,1fr) auto}.g-side{font-size:12.5px;font-weight:700;text-align:center}
  .g-side2{display:grid;grid-template-columns:1fr 1fr;gap:4px;padding:4px;border-radius:16px;background:var(--soft);border:1px solid var(--line);margin-top:14px}
  .g-side2 button{padding:10px;border-radius:12px;font-weight:700;color:var(--muted)}
  .g-side2 button.b[aria-pressed="true"]{background:#ffdbe1;color:#c8243f}.g-side2 button.s[aria-pressed="true"]{background:#dce9ff;color:#2459c9}
  .g-qty{display:flex;align-items:center;gap:8px;background:var(--soft);border:1px solid var(--line);border-radius:16px;padding:4px 16px}
  .g-qty input{flex:1;min-width:0;border:0;background:none;font:inherit;font-family:var(--f-disp,inherit);font-size:22px;font-weight:700;text-align:right;color:var(--fg);padding:8px 0}
  .g-qty input:focus{outline:none}.g-qty:focus-within{border-color:var(--line2,var(--brand2));box-shadow:0 0 0 4px var(--lav-s,#efedff)}
  .cta.g-buy{background:linear-gradient(135deg,#ffd3db,#ffb4c1);color:#c8243f;box-shadow:0 10px 22px rgba(239,69,101,.16)}.cta.g-sell{background:linear-gradient(135deg,#d6e6ff,#b8d3ff);color:#2459c9;box-shadow:0 10px 22px rgba(61,123,242,.16)}.cta[disabled]{opacity:.4}
  button.cta{border:0;cursor:pointer;width:100%}
  .g-review{margin:8px 0 0;padding-left:18px;line-height:1.6;font-size:14.5px;display:flex;flex-direction:column;gap:4px}
  .g-msg.down{background:#eaf1ff;color:#2459c9}
  .g-line{display:flex;flex-direction:column;gap:2px;margin-top:12px;padding:12px 14px;border-radius:14px;background:var(--lav-s,#efedff);text-decoration:none;color:inherit;font-size:14.5px}
  .g-cancel{border:1px solid var(--line2,#dcd8ff);background:#fff;border-radius:10px;padding:6px 10px;font:inherit;font-size:12.5px;color:var(--muted)}
  .g-quit{display:block;margin:14px auto 0;color:var(--muted);font-size:13.5px;text-decoration:underline}
  .g-end{text-align:center}.g-end .ic{font-size:40px}.g-end .mkt{text-align:left}.g-end .tiles{text-align:left}`;
  document.head.appendChild(css);

  window.Game = { view, _state: () => G };
})();
