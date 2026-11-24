/* '추천 성적' 화면 (#track) — 2026-11-24 사용자: "AI대결 이제 없애, 나 혼자 쓰는 거니 모의로 월요일 너가 추천한 걸 샀을 때
   금요일날 수익이 나는지, 너를 따라서 투자했을 때 성공률이 얼마나 될런지 보려는 거야".
   data/report/track.json (report.yml 이 보고 때마다 ai_trading.report.ledger() 로 만듦)을 보여 준다.
   index.html 이 Track.view() 를 부른다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n || 0).toLocaleString("ko-KR");
  const pct = x => (x == null ? "-" : (x > 0 ? "+" : "") + Number(x).toFixed(2) + "%");
  const cls = x => (x > 0.004 ? "up" : x < -0.004 ? "down" : "flat");
  const md = d => (d ? d.slice(5).replace("-", ".") : "");
  let T = null, tried = false;
  const loadLS = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const symOf = code => { const S = (window.__SC || {}).stocks || {}; return Object.keys(S).find(k => S[k].code === code) || null; };
  const buyLink = (code, name) => { const sym = symOf(code); return sym ? `<a href="#game/${encodeURIComponent(sym)}"><b>${esc(name)}</b></a>` : `<b>${esc(name)}</b>`; };

  /* 내 모의투자(거래하기) 기록 → 실력 카드. 기록은 이 휴대폰에만 있음 (game.js 와 같은 저장소) */
  function mine() {
    const G = loadLS("aiLab.game.v1", null), hist = loadLS("aiLab.games.v1", []), SC = window.__SC;
    if (!G) return null;
    const px = sym => (SC && SC.stocks[sym] ? SC.stocks[sym].price : null);
    const base = (G.cash0 || 10_000_000) + (G.added || 0);
    const pos = Object.entries(G.pos || {}).map(([sym, p]) => ({ sym, name: p.name, val: p.qty * (px(sym) ?? p.last ?? p.avg) }));
    const eq = (G.cash || 0) + pos.reduce((a, p) => a + p.val, 0);
    const trades = [...(G.trades || []), ...[]];
    const sells = trades.filter(t => t.side === "S"), buys = trades.filter(t => t.side === "B");
    const wins = sells.filter(t => t.pnl > 0), loss = sells.filter(t => t.pnl < 0);
    // 추천을 따라 산 매수인지: 매수일 기준 7일 안에 나온 주간·새 추천에 있던 종목
    const recs = [];
    (T.weeks || []).forEach(w => w.picks.forEach(p => recs.push([p.code, w.monday])));
    (T.fresh || []).forEach(p => recs.push([p.code, p.date]));
    const isRec = t => { const c = String(t.sym).split(".")[0]; return recs.some(([rc, d]) => rc === c && t.d >= d && (new Date(t.d) - new Date(d)) / 864e5 <= 7); };
    const followed = buys.filter(isRec).length;
    const pnlBy = f => sells.filter(t => f(t)).reduce((a, t) => a + (t.pnl || 0), 0);
    // 물타기: 같은 종목을 이전 매수가보다 싸게 또 산 횟수
    let avgDown = 0; const lastBuy = {};
    buys.forEach(t => { if (lastBuy[t.sym] != null && t.p < lastBuy[t.sym]) avgDown++; lastBuy[t.sym] = t.p; });
    const maxW = eq > 0 && pos.length ? Math.max(...pos.map(p => p.val)) / eq * 100 : 0;
    return { G, hist, eq, ret: (eq / base - 1) * 100, nSell: sells.length, win: sells.length ? wins.length / sells.length * 100 : null,
      avgWin: wins.length ? wins.reduce((a, t) => a + t.pnl, 0) / wins.length : null, avgLoss: loss.length ? loss.reduce((a, t) => a + t.pnl, 0) / loss.length : null,
      nBuy: buys.length, followed, recPnl: pnlBy(isRec), ownPnl: pnlBy(t => !isRec(t)), avgDown, maxW, cashW: eq > 0 ? (G.cash || 0) / eq * 100 : 100 };
  }

  const chk = (ok, label, now) => `<li class="tk-ck ${ok === true ? "ok" : ok === false ? "no" : ""}"><span>${ok === true ? "✅" : ok === false ? "⬜" : "⏳"}</span><div><b>${label}</b><div class="tk-s">${now}</div></div></li>`;

  function trustCard(s, M) {
    const items = [
      [s.weeks >= 12 ? true : null, "모의 기록 12주 이상", `지금 ${s.weeks || 0}주 / 12주 (운이 아닌 실력인지 보려면 최소 3달)`],
      [s.weeks ? s.win_rate >= 55 : null, "주간 성공률 55% 이상", s.weeks ? `지금 ${s.win_rate}%` : "첫 주 결과 대기"],
      [s.weeks ? s.cum > s.kospi_cum : null, "누적 수익이 같은 기간 코스피보다 높음", s.weeks ? `추천 ${pct(s.cum)} vs 코스피 ${pct(s.kospi_cum)}` : "첫 주 결과 대기"],
      [s.weeks ? s.worst_week >= -5 : null, "가장 나빴던 주도 -5% 안쪽", s.weeks ? `최악의 주 ${pct(s.worst_week)}` : "첫 주 결과 대기"],
      [M && M.nSell >= 10 ? M.ret > 0 : null, "내 모의계좌도 수익 (매도 10번 이상)", M ? `내 수익률 ${pct(M.ret)} · 매도 ${M.nSell}번` : "거래하기 탭에서 모의투자를 시작하세요"],
    ];
    const pass = items.filter(x => x[0] === true).length;
    return `<section class="card"><h2>실전 투자, 언제 해도 될까?</h2>
      <p class="sub">5개를 모두 통과하기 전엔 실제 돈을 넣지 마세요. 통과해도 처음엔 잃어도 괜찮은 소액부터예요.</p>
      <div class="tk-bar"><i style="width:${pass * 20}%"></i></div><p class="sub"><b>${pass}/5 통과</b>${pass === 5 ? " · 소액으로 시작해 볼 만해요" : " · 아직 모의투자로 연습할 때예요"}</p>
      <ul class="tk-cks">${items.map(x => chk(...x)).join("")}</ul></section>`;
  }

  function mineCard(M) {
    if (!M) return `<section class="card"><h2>내 모의투자 실력</h2><p class="sub">거래하기 탭에서 모의투자를 시작하고, 위 추천 종목 이름을 눌러 그대로 사 보세요. 여기서 내 성적과 습관을 같이 봐 드려요.</p><a class="pclink" href="#game">거래하기 시작 ▶</a></section>`;
    const stat2 = (l, v, sub, c = "") => stat(l, v, sub, c);
    return `<section class="card"><h2>내 모의투자 실력</h2><p class="sub">거래하기 탭 기록 기준 (이 휴대폰에만 저장)</p>
      <div class="tk-grid">
        ${stat2("내 수익률", pct(M.ret), `평가금 ${won(M.eq)}원`, cls(M.ret))}
        ${stat2("매도 승률", M.win == null ? "-" : Math.round(M.win) + "%", `매도 ${M.nSell}번`)}
        ${stat2("이길 때 평균", M.avgWin == null ? "-" : "+" + won(M.avgWin) + "원", M.avgLoss == null ? "" : `질 때 평균 ${won(M.avgLoss)}원`)}
        ${stat2("추천 따라 산 비율", M.nBuy ? Math.round(M.followed / M.nBuy * 100) + "%" : "-", `매수 ${M.nBuy}번 중 ${M.followed}번`)}
      </div>
      ${M.nSell ? `<p class="sub" style="margin-top:10px">실현 손익: 추천 따라 산 것 <b class="${cls(M.recPnl)}">${M.recPnl >= 0 ? "+" : ""}${won(M.recPnl)}원</b> · 내 판단으로 산 것 <b class="${cls(M.ownPnl)}">${M.ownPnl >= 0 ? "+" : ""}${won(M.ownPnl)}원</b></p>` : ""}
    </section>`;
  }

  function rulesCard(M) {
    const r = [
      [M ? M.maxW <= 30 : null, "한 종목·한 테마에 몰빵하지 않기", M ? `내 계좌 최대 한 종목 비중 ${Math.round(M.maxW)}% (30% 이하 권장)` : "반도체 ETF 하나에 몰리면 업종이 꺾일 때 같이 무너져요"],
      [true, "사기 전에 손절가부터 정하기", "추천마다 손절가(-5%)가 있어요. 모의투자도 -5%에서 자동 손절돼요"],
      [M ? M.avgDown === 0 : null, "떨어진다고 물타기 하지 않기", M ? `더 싸게 또 산 횟수 ${M.avgDown}번` : "계획 없는 물타기가 손실을 -50%까지 키워요"],
      [M ? M.cashW >= 20 : null, "현금 20% 남겨 두기", M ? `지금 현금 비중 ${Math.round(M.cashW)}%` : "기회가 와도 살 돈이 있어야 해요"],
      [null, "레버리지·테마 ETF는 오래 들고 있지 않기", "레버리지 ETF는 오르내림을 반복하면 지수가 제자리여도 녹아요"],
    ];
    return `<section class="card"><h2>잃지 않는 습관 5가지</h2><p class="sub">수익보다 먼저 큰 손실을 피하는 게 실력이에요. -50%를 되찾으려면 +100%가 필요해요.</p>
      <ul class="tk-cks">${r.map(x => chk(...x)).join("")}</ul></section>`;
  }

  function load() {
    if (tried) return; tried = true;
    fetch("../data/report/track.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => {
      T = d || {}; window.dispatchEvent(new HashChangeEvent("hashchange"));
    }).catch(() => { T = {}; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  }

  const tag = p => {
    const c = p.why === "익절" ? "up" : p.why === "손절" ? "down" : "flat";
    return `<span class="tk-tag ${c}">${esc(p.why)}${p.on && p.done ? " " + md(p.on) : ""}</span>`;
  };

  function stat(label, val, sub, c = "") {
    return `<div class="tk-stat"><div class="tk-l">${label}</div><div class="tk-v ${c}">${val}</div>${sub ? `<div class="tk-s">${sub}</div>` : ""}</div>`;
  }

  function view() {
    load();
    if (!T) return `<div class="card"><div class="skel" style="width:40%"></div><div class="skel"></div><div class="skel" style="width:70%"></div></div>`;
    const s = T.summary || {}, weeks = T.weeks || [], fresh = T.fresh || [], M = mine();
    const top = `<section class="card"><h2>본부장 추천 따라 하기 · 모의 성적</h2>
      <p class="sub">월요일 추천 3종목을 비중대로 샀다면 금요일에 얼마나 벌었을까요? 매 보고 때 새로 계산해요.</p>
      <div class="tk-grid">
        ${stat("주간 성공률", s.win_rate == null ? "-" : s.win_rate + "%", s.weeks ? `${s.weeks}주 중 ${s.win_weeks}주 수익` : "첫 결과는 금요일 오후")}
        ${stat("누적 수익률", pct(s.cum), s.weeks ? `같은 기간 코스피 ${pct(s.kospi_cum)}` : "", cls(s.cum))}
        ${stat("종목 적중", s.pick_n ? `${s.pick_hit}/${s.pick_n}` : "-", "끝난 주의 종목 중 수익 난 수")}
        ${stat("새 추천 적중", s.fresh_n ? `${s.fresh_hit}/${s.fresh_n}` : "-", s.fresh_n ? `5거래일 평균 ${pct(s.fresh_avg)}` : "5거래일 지나면 집계", cls(s.fresh_avg))}
      </div></section>`;
    const wk = weeks.map(w => `<section class="card"><div class="tk-h"><h2>${md(w.monday)} ~ ${md(w.friday)} 주</h2>
        <b class="${cls(w.ret)}">${pct(w.ret)}</b></div><p class="sub">${w.done ? "결과 확정" : "진행 중 · 지금 값 기준"}${w.kospi != null ? ` · 같은 기간 코스피 <b class="${cls(w.kospi)}">${pct(w.kospi)}</b>${w.ret > w.kospi ? " (추천이 나음)" : " (코스피가 나음)"}` : ""} · 종목 이름을 누르면 모의로 살 수 있어요</p>
        <table class="tk-t"><thead><tr><th>종목</th><th>비중</th><th>진입가</th><th>매도/현재</th><th>수익률</th></tr></thead><tbody>
        ${w.picks.map(p => `<tr><td>${buyLink(p.code, p.name)}<div class="tk-s">손절 ${won(p.stop)} · 익절 ${won(p.target)}</div></td><td>${p.weight || 0}%</td>
          <td>${won(p.entry)}</td><td>${won(p.exit)}<div>${tag(p)}</div></td><td class="${cls(p.ret)}"><b>${pct(p.ret)}</b></td></tr>`).join("")}
        </tbody></table></section>`).join("");
    const fr = fresh.length ? `<section class="card"><h2>보고마다 새 추천 (5거래일)</h2><p class="sub">오전 보고 추천은 그날부터, 오후 보고 추천은 다음 날부터 5거래일 보유로 계산해요.</p>
        <table class="tk-t"><thead><tr><th>추천</th><th>종목</th><th>진입가</th><th>매도/현재</th><th>수익률</th></tr></thead><tbody>
        ${fresh.map(p => `<tr><td>${md(p.date)} ${p.slot === "am" ? "오전" : "오후"}</td><td>${buyLink(p.code, p.name)}</td><td>${won(p.entry)}</td>
          <td>${won(p.exit)}<div>${tag(p)}</div></td><td class="${cls(p.ret)}"><b>${pct(p.ret)}</b></td></tr>`).join("")}
        </tbody></table></section>` : "";
    const empty = !weeks.length && !fresh.length ? `<div class="card"><h2>아직 기록이 없어요</h2><p class="sub">월요일 오전 보고의 추천부터 쌓여요.</p></div>` : "";
    return `<style>
      .tk-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
      .tk-stat{background:#f6f5ff;border-radius:14px;padding:12px}
      .tk-l{font-size:12.5px;color:var(--muted)}.tk-v{font-size:22px;font-weight:800;margin-top:2px}.tk-s{font-size:11.5px;color:var(--muted);margin-top:2px}
      .tk-h{display:flex;justify-content:space-between;align-items:baseline}.tk-h b{font-size:20px}
      .tk-t{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
      .tk-t th{font-size:11.5px;color:var(--muted);font-weight:600;text-align:left;padding:6px 4px;border-bottom:1px solid var(--line)}
      .tk-t td{padding:8px 4px;border-bottom:1px solid var(--line);vertical-align:top}
      .tk-t td:nth-child(n+3),.tk-t th:nth-child(n+3){text-align:right}
      .tk-tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:8px;background:#f1f0f5;margin-top:2px}
      .tk-bar{height:10px;border-radius:6px;background:#eeedf7;margin-top:12px;overflow:hidden}.tk-bar i{display:block;height:100%;background:linear-gradient(90deg,#8f7cff,#6c5ce7)}
      .tk-cks{list-style:none;padding:0;margin:10px 0 0}.tk-ck{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px}.tk-ck:last-child{border-bottom:0}
      .tk-ck>span{font-size:16px;line-height:1.2}.tk-t a{color:inherit;text-decoration:underline;text-decoration-color:#c9c3ff;text-underline-offset:3px}
    </style>${top}${trustCard(s, M)}${wk}${fr}${mineCard(M)}${rulesCard(M)}${empty}
    <p class="sub" style="margin:14px 4px 90px">${esc(T.rule || "")}${T.made ? ` · 계산 ${esc(T.made)}` : ""}</p>`;
  }

  window.Track = { view };
})();
