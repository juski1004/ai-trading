/* '추천 성적' 화면 (#track)
   2026-11-24 사용자: "AI대결 없애. 월요일 너가 추천한 걸 샀을 때 금요일날 수익이 나는지, 따라 투자했을 때 성공률이 얼마나 될런지"
   2026-11-24 사용자: "내가 사고파는 단계를 없애고, 추천대로 얼마에 몇 주 몇 % 사고, 손절가 얼마에 몇 주, 익절가 얼마에 몇 주 걸고 한 걸
                      보여 주고 금요일날 결과를 보여 주는 시뮬레이션을 한눈에"
   → 모의 자금(1천만·3천만·1억, 이 휴대폰에 기억)으로 주간 추천의 '월요일 주문서'(매수·손절·익절 주문)와 '금요일 결과'를 한 장에.
   데이터: data/report/track.json (report.yml 이 보고 때마다 ai_trading.report.ledger() 로 만듦). index.html 이 Track.view() 를 부른다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n || 0).toLocaleString("ko-KR");
  const sw = n => (n > 0 ? "+" : n < 0 ? "−" : "") + won(Math.abs(n));
  const pct = x => (x == null ? "-" : (x > 0 ? "+" : "") + Number(x).toFixed(2) + "%");
  const p1 = x => (x > 0 ? "+" : "") + Number(x).toFixed(1) + "%";
  const cls = x => (x > 0.004 ? "up" : x < -0.004 ? "down" : "flat");
  const md = d => (d ? d.slice(5).replace("-", ".") : "");
  const CAPS = [[10_000_000, "1천만"], [30_000_000, "3천만"], [100_000_000, "1억"]], CKEY = "aiLab.trackCap.v1";
  const getCap = () => { try { return +localStorage.getItem(CKEY) || CAPS[0][0]; } catch (e) { return CAPS[0][0]; } };
  let T = null, tried = false;

  function load() {
    if (tried) return; tried = true;
    fetch("../data/report/track.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => {
      T = d || {}; window.__TRACK = T; window.dispatchEvent(new HashChangeEvent("hashchange"));
    }).catch(() => { T = {}; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-tkcap]"); if (!b) return;
    try { localStorage.setItem(CKEY, b.dataset.tkcap); } catch (err) {}
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });

  const stat = (label, val, sub, c = "") =>
    `<div class="tk-stat"><div class="tk-l">${label}</div><div class="tk-v ${c}">${val}</div>${sub ? `<div class="tk-s">${sub}</div>` : ""}</div>`;
  const chk = (ok, label, now, ic) => `<li class="tk-ck"><span>${ic || (ok === true ? "✅" : ok === false ? "⬜" : "⏳")}</span><div><b>${label}</b><div class="tk-s">${now}</div></div></li>`;

  /* 모의 자금으로 주문 수량·금액 계산 (비중대로, 1주 단위 내림) */
  function plan(picks, cap) {
    const rows = picks.map(p => {
      const qty = Math.floor(cap * (p.weight || 0) / 100 / p.entry), cost = qty * p.entry;
      const out = qty * p.exit, pnl = out - cost;
      return { ...p, qty, cost, lossAt: qty * ((p.stop || p.entry) - p.entry), gainAt: qty * ((p.target || p.entry) - p.entry), out, pnl };
    });
    const cost = rows.reduce((a, r) => a + r.cost, 0), pnl = rows.reduce((a, r) => a + r.pnl, 0);
    return { rows, cost, cash: cap - cost, pnl, end: cap + pnl, ret: pnl / cap * 100,
      worst: rows.reduce((a, r) => a + r.lossAt, 0), best: rows.reduce((a, r) => a + r.gainAt, 0) };
  }

  const resultTxt = r => r.why === "손절" ? `<b class="down">손절 체결</b> ${md(r.on)} · ${won(r.exit)}원`
    : r.why === "익절" ? `<b class="up">익절 체결</b> ${md(r.on)} · ${won(r.exit)}원`
    : r.why === "기간 종료" ? `금요일 종가 매도 · ${won(r.exit)}원`
    : r.why === "대기" ? "아직 체결 전" : `보유 중 · 지금 ${won(r.exit)}원`;

  function weekCard(w, cap) {
    const P = plan(w.picks, cap);
    const orders = P.rows.map(r => `<div class="tk-o">
        <div class="tk-on"><b>${esc(r.name)}</b><span>비중 ${r.weight || 0}%</span></div>
        <div class="tk-ol buy"><i>매수</i><span>${won(r.entry)}원 × <b>${won(r.qty)}주</b></span><em>${won(r.cost)}원</em></div>
        <div class="tk-ol stop"><i>손절</i><span>${won(r.stop)}원 (${p1((r.stop / r.entry - 1) * 100)}) · ${won(r.qty)}주 전량</span><em class="down">${sw(r.lossAt)}원</em></div>
        <div class="tk-ol take"><i>익절</i><span>${won(r.target)}원 (${p1((r.target / r.entry - 1) * 100)}) · ${won(r.qty)}주 전량</span><em class="up">${sw(r.gainAt)}원</em></div>
        <div class="tk-ol res"><i>${w.done ? "결과" : "지금"}</i><span>${resultTxt(r)}</span><em class="${cls(r.pnl)}">${sw(r.pnl)}원<br><small>${pct(r.ret)}</small></em></div>
      </div>`).join("");
    return `<section class="card">
      <div class="tk-h"><h2>${md(w.monday)}(월) ~ ${md(w.friday)}(금)</h2><span class="tk-badge ${w.done ? "" : "live"}">${w.done ? "결과 확정" : "진행 중"}</span></div>
      <p class="sub">모의 자금 ${won(cap)}원으로 월요일에 이렇게 주문했다면</p>
      <div class="tk-sum">
        <div><span>투자</span><b>${won(P.cost)}원</b><small>현금 ${won(P.cash)}원 남김</small></div>
        <div><span>손절 다 맞으면</span><b class="down">${sw(P.worst)}원</b><small>${p1(P.worst / cap * 100)}</small></div>
        <div><span>익절 다 되면</span><b class="up">${sw(P.best)}원</b><small>${p1(P.best / cap * 100)}</small></div>
      </div>
      ${orders}
      <div class="tk-final ${cls(P.pnl)}">
        <div><span>${w.done ? "금요일 결과" : "지금까지"}</span><b>${sw(P.pnl)}원 (${pct(P.ret)})</b><small>${won(cap)}원 → ${won(P.end)}원</small></div>
        ${w.kospi != null ? `<div class="tk-vs">같은 기간 코스피 <b class="${cls(w.kospi)}">${pct(w.kospi)}</b> · ${P.ret > w.kospi ? "추천이 코스피보다 나음 👍" : "코스피가 추천보다 나음"}</div>` : ""}
      </div>
    </section>`;
  }

  function trustCard(s) {
    const items = [
      [s.weeks >= 12 ? true : null, "모의 기록 12주 이상", `지금 ${s.weeks || 0}주 / 12주 (운이 아니라 실력인지 보려면 최소 3달)`],
      [s.weeks ? s.win_rate >= 55 : null, "주간 성공률 55% 이상", s.weeks ? `지금 ${s.win_rate}% (${s.weeks}주 중 ${s.win_weeks}주 수익)` : "첫 주 결과 대기 (금요일 오후)"],
      [s.weeks ? s.cum > s.kospi_cum : null, "누적 수익이 같은 기간 코스피보다 높음", s.weeks ? `추천 ${pct(s.cum)} vs 코스피 ${pct(s.kospi_cum)}` : "첫 주 결과 대기"],
      [s.weeks ? s.worst_week >= -5 : null, "가장 나빴던 주도 -5% 안쪽", s.weeks ? `최악의 주 ${pct(s.worst_week)}` : "첫 주 결과 대기"],
      [s.fresh_n >= 10 ? (s.fresh_hit / s.fresh_n) >= 0.55 : null, "보고마다 새 추천도 55% 이상 적중 (10종목 이상)", s.fresh_n ? `지금 ${s.fresh_hit}/${s.fresh_n} · 평균 ${pct(s.fresh_avg)}` : "5거래일 지나면 집계"],
    ];
    const pass = items.filter(x => x[0] === true).length;
    return `<section class="card"><h2>실전 투자, 언제 해도 될까?</h2>
      <p class="sub">5개를 모두 통과하기 전엔 실제 돈을 넣지 마세요. 통과해도 처음엔 잃어도 괜찮은 소액부터예요.</p>
      <div class="tk-bar"><i style="width:${pass * 20}%"></i></div><p class="sub"><b>${pass}/5 통과</b>${pass === 5 ? " · 소액으로 시작해 볼 만해요" : " · 아직 지켜볼 때예요"}</p>
      <ul class="tk-cks">${items.map(x => chk(...x)).join("")}</ul></section>`;
  }

  function freshCard(fresh, cap) {
    if (!fresh.length) return "";
    const per = cap / 2;  // 보고마다 2종목: 한 보고에 자금 절반씩 쓴다고 보고 수량 계산
    return `<section class="card"><h2>보고마다 새 추천 (5거래일 보유)</h2>
      <p class="sub">보고 한 번에 ${won(per)}원을 비중대로 샀다고 계산 · 오전 추천은 그날부터, 오후 추천은 다음 날부터</p>
      <table class="tk-t"><thead><tr><th>추천</th><th>종목·주문</th><th>결과</th><th>손익</th></tr></thead><tbody>
      ${fresh.map(p => { const q = Math.floor(per * (p.weight || 0) / 100 / p.entry), pnl = q * (p.exit - p.entry);
        return `<tr><td>${md(p.date)}<br>${p.slot === "am" ? "오전" : "오후"}</td>
          <td><b>${esc(p.name)}</b><div class="tk-s">${won(p.entry)}원 × ${won(q)}주 · 손절 ${won(p.stop)} · 익절 ${won(p.target)}</div></td>
          <td class="tk-s">${resultTxt(p)}</td><td class="${cls(pnl)}"><b>${sw(pnl)}</b><div class="tk-s">${pct(p.ret)}</div></td></tr>`; }).join("")}
      </tbody></table></section>`;
  }

  const rulesCard = () => `<section class="card"><h2>잃지 않는 습관</h2><p class="sub">-50%를 되찾으려면 +100%가 필요해요. 그래서 수익보다 큰 손실을 피하는 게 먼저예요.</p>
    <ul class="tk-cks">
      ${chk(null, "사기 전에 손절가부터 정하기", "위 주문서처럼 매수와 동시에 손절·익절 주문을 같이 걸어요", "📌")}
      ${chk(null, "한 종목·한 테마에 몰빵하지 않기", "추천도 3종목으로 나누고, 한 종목은 절반을 넘지 않아요", "📌")}
      ${chk(null, "떨어진다고 물타기 하지 않기", "손절가에 닿으면 계획대로 팔아요. 계획 없는 물타기가 손실을 키워요", "📌")}
      ${chk(null, "레버리지·테마 ETF는 오래 들고 있지 않기", "오르내림이 반복되면 지수가 제자리여도 값이 녹아요", "📌")}
    </ul></section>`;

  function view() {
    load();
    if (!T) return `<div class="card"><div class="skel" style="width:40%"></div><div class="skel"></div><div class="skel" style="width:70%"></div></div>`;
    const s = T.summary || {}, weeks = T.weeks || [], fresh = T.fresh || [], cap = getCap();
    const capBtns = CAPS.map(([v, l]) => `<button type="button" data-tkcap="${v}" class="${v === cap ? "on" : ""}">${l}</button>`).join("");
    const top = `<section class="card"><h2>본부장 추천 따라 하기 · 모의 성적</h2>
      <p class="sub">직접 사고팔 필요 없어요. 월요일 추천대로 주문했다고 치고 금요일 결과를 자동으로 계산해요.</p>
      <div class="tk-cap"><span>모의 자금</span>${capBtns}</div>
      <div class="tk-grid">
        ${stat("주간 성공률", s.win_rate == null ? "-" : s.win_rate + "%", s.weeks ? `${s.weeks}주 중 ${s.win_weeks}주 수익` : "첫 결과는 금요일 오후")}
        ${stat("누적 수익률", pct(s.cum), s.weeks ? `코스피 ${pct(s.kospi_cum)}` : "", cls(s.cum))}
        ${stat("누적 손익", s.weeks ? sw(cap * s.cum / 100) + "원" : "-", s.weeks ? `${won(cap)}원 기준` : "", cls(s.cum))}
        ${stat("코스피보다 나은 주", s.weeks ? `${s.beat_weeks}/${s.weeks}` : "-", "")}
      </div></section>`;
    const empty = !weeks.length && !fresh.length ? `<div class="card"><h2>아직 기록이 없어요</h2><p class="sub">월요일 오전 보고의 추천부터 쌓여요.</p></div>` : "";
    return `<style>
      .tk-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}
      .tk-stat{background:#f6f5ff;border-radius:14px;padding:12px}
      .tk-l{font-size:12.5px;color:var(--muted)}.tk-v{font-size:21px;font-weight:800;margin-top:2px}.tk-s{font-size:11.5px;color:var(--muted);margin-top:2px}
      .tk-cap{display:flex;align-items:center;gap:6px;margin-top:12px;font-size:12.5px;color:var(--muted)}
      .tk-cap button{border:1px solid var(--line);background:#fff;border-radius:16px;padding:5px 12px;font-size:13px;font-weight:700;color:#555}
      .tk-cap button.on{background:#6c5ce7;border-color:#6c5ce7;color:#fff}
      .tk-h{display:flex;justify-content:space-between;align-items:center}
      .tk-badge{font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:10px;background:#eef7f0;color:#2f8f4e}.tk-badge.live{background:#fff4e5;color:#c07000}
      .tk-sum{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:12px 0 4px}
      .tk-sum div{background:#f7f7fb;border-radius:12px;padding:9px 8px;display:flex;flex-direction:column;gap:1px}
      .tk-sum span,.tk-sum small{font-size:11px;color:var(--muted)}.tk-sum b{font-size:14px}
      .tk-o{border:1px solid var(--line);border-radius:14px;padding:10px 12px;margin-top:10px}
      .tk-on{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}.tk-on b{font-size:15px}.tk-on span{font-size:12px;color:var(--muted)}
      .tk-ol{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:5px 0;border-top:1px dashed #ecebf3}
      .tk-ol i{font-style:normal;font-size:11px;font-weight:800;border-radius:6px;padding:2px 6px;flex:none}
      .tk-ol.buy i{background:#ece9ff;color:#5b4bd6}.tk-ol.stop i{background:#e8f1ff;color:#2c6fd6}.tk-ol.take i{background:#ffe9ee;color:#d6334f}.tk-ol.res i{background:#222;color:#fff}
      .tk-ol span{flex:1}.tk-ol em{font-style:normal;font-weight:700;text-align:right;white-space:nowrap}.tk-ol em small{font-weight:600;font-size:11px}
      .tk-final{margin-top:12px;border-radius:14px;padding:12px;background:#f6f5ff}
      .tk-final.up{background:#fff0f3}.tk-final.down{background:#eef4ff}
      .tk-final>div:first-child{display:flex;flex-direction:column}.tk-final span{font-size:12px;color:var(--muted)}.tk-final b{font-size:20px}.tk-final small{font-size:12px;color:var(--muted)}
      .tk-vs{font-size:12.5px;margin-top:6px}.tk-vs b{font-size:inherit}
      .tk-t{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
      .tk-t th{font-size:11.5px;color:var(--muted);font-weight:600;text-align:left;padding:6px 4px;border-bottom:1px solid var(--line)}
      .tk-t td{padding:8px 4px;border-bottom:1px solid var(--line);vertical-align:top}.tk-t td:last-child,.tk-t th:last-child{text-align:right}
      .tk-bar{height:10px;border-radius:6px;background:#eeedf7;margin-top:12px;overflow:hidden}.tk-bar i{display:block;height:100%;background:linear-gradient(90deg,#8f7cff,#6c5ce7)}
      .tk-cks{list-style:none;padding:0;margin:10px 0 0}.tk-ck{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px}.tk-ck:last-child{border-bottom:0}
      .tk-ck>span{font-size:16px;line-height:1.2}
    </style>${top}${weeks.map(w => weekCard(w, cap)).join("")}${trustCard(s)}${freshCard(fresh, cap)}${rulesCard()}${empty}
    <p class="sub" style="margin:14px 4px 90px">${esc(T.rule || "")} 손절·익절이 같은 날 둘 다 닿으면 손절로 계산.${T.made ? ` · 계산 ${esc(T.made)}` : ""}</p>`;
  }

  /* 홈 카드: 이번 주 추천 모의 성적 한 줄 */
  function homeCard() {
    load(); if (!T || !(T.weeks || []).length) return "";
    const w = T.weeks[0], cap = getCap(), P = plan(w.picks, cap), s = T.summary || {};
    return `<section class="card"><a href="#track" style="color:inherit;text-decoration:none;display:block">
      <div class="hd"><div><h2>이번 주 추천 따라 하기</h2><p class="sub">${md(w.monday)}(월) 추천 ${w.picks.map(p => esc(p.name)).join("·")} · ${w.done ? "결과 확정" : "진행 중"}</p></div><span class="rp-go" style="white-space:nowrap;align-self:center">보기 ›</span></div>
      <div style="display:flex;align-items:baseline;gap:10px;margin-top:8px"><b class="${cls(P.pnl)}" style="font-size:22px">${sw(P.pnl)}원</b><span class="${cls(P.ret)}">${pct(P.ret)}</span>
      ${w.kospi != null ? `<span class="sub">코스피 ${pct(w.kospi)}</span>` : ""}</div>
      <p class="sub">모의 자금 ${won(cap)}원 기준${s.weeks ? ` · 누적 ${s.weeks}주 성공률 ${s.win_rate}%` : ""}</p></a></section>`;
  }

  /* 종목 화면: 이 종목을 본부장이 추천한 기록과 결과 */
  function detail(sym) {
    load(); if (!T) return "";
    const code = String(sym).split(".")[0], rows = [];
    (T.weeks || []).forEach(w => w.picks.forEach(p => { if (p.code === code) rows.push({ when: `${md(w.monday)} 주간 추천`, ...p }); }));
    (T.fresh || []).forEach(p => { if (p.code === code) rows.push({ when: `${md(p.date)} ${p.slot === "am" ? "오전" : "오후"} 새 추천`, ...p }); });
    if (!rows.length) return "";
    return `<section class="card"><h2>본부장 추천 기록</h2><p class="sub">이 종목을 추천했던 때와 모의 결과</p>
      <table class="tk-t" style="width:100%;border-collapse:collapse;margin-top:8px;font-size:13px"><tbody>${rows.map(r => `<tr><td style="padding:7px 0;border-bottom:1px solid var(--line)"><b>${r.when}</b><div class="sub">진입 ${won(r.entry)} · 손절 ${won(r.stop)} · 익절 ${won(r.target)}</div></td>
        <td style="text-align:right;border-bottom:1px solid var(--line)"><b class="${cls(r.ret)}">${pct(r.ret)}</b><div class="sub">${esc(r.why)}</div></td></tr>`).join("")}</tbody></table></section>`;
  }

  window.Track = { view, homeCard, detail };
})();
