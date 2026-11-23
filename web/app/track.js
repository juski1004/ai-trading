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
    const s = T.summary || {}, weeks = T.weeks || [], fresh = T.fresh || [];
    const top = `<section class="card"><h2>본부장 추천 따라 하기 · 모의 성적</h2>
      <p class="sub">월요일 추천 3종목을 비중대로 샀다면 금요일에 얼마나 벌었을까요? 매 보고 때 새로 계산해요.</p>
      <div class="tk-grid">
        ${stat("주간 성공률", s.win_rate == null ? "-" : s.win_rate + "%", s.weeks ? `${s.weeks}주 중 ${s.win_weeks}주 수익` : "첫 결과는 금요일 오후")}
        ${stat("누적 수익률", pct(s.cum), s.weeks ? `주 평균 ${pct(s.avg_week)}` : "", cls(s.cum))}
        ${stat("종목 적중", s.pick_n ? `${s.pick_hit}/${s.pick_n}` : "-", "끝난 주의 종목 중 수익 난 수")}
        ${stat("새 추천 적중", s.fresh_n ? `${s.fresh_hit}/${s.fresh_n}` : "-", s.fresh_n ? `5거래일 평균 ${pct(s.fresh_avg)}` : "5거래일 지나면 집계", cls(s.fresh_avg))}
      </div></section>`;
    const wk = weeks.map(w => `<section class="card"><div class="tk-h"><h2>${md(w.monday)} ~ ${md(w.friday)} 주</h2>
        <b class="${cls(w.ret)}">${pct(w.ret)}</b></div><p class="sub">${w.done ? "결과 확정" : "진행 중 · 지금 값 기준"}</p>
        <table class="tk-t"><thead><tr><th>종목</th><th>비중</th><th>진입가</th><th>매도/현재</th><th>수익률</th></tr></thead><tbody>
        ${w.picks.map(p => `<tr><td><b>${esc(p.name)}</b><div class="tk-s">손절 ${won(p.stop)} · 익절 ${won(p.target)}</div></td><td>${p.weight || 0}%</td>
          <td>${won(p.entry)}</td><td>${won(p.exit)}<div>${tag(p)}</div></td><td class="${cls(p.ret)}"><b>${pct(p.ret)}</b></td></tr>`).join("")}
        </tbody></table></section>`).join("");
    const fr = fresh.length ? `<section class="card"><h2>보고마다 새 추천 (5거래일)</h2><p class="sub">오전 보고 추천은 그날부터, 오후 보고 추천은 다음 날부터 5거래일 보유로 계산해요.</p>
        <table class="tk-t"><thead><tr><th>추천</th><th>종목</th><th>진입가</th><th>매도/현재</th><th>수익률</th></tr></thead><tbody>
        ${fresh.map(p => `<tr><td>${md(p.date)} ${p.slot === "am" ? "오전" : "오후"}</td><td><b>${esc(p.name)}</b></td><td>${won(p.entry)}</td>
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
    </style>${top}${wk}${fr}${empty}
    <p class="sub" style="margin:14px 4px 90px">${esc(T.rule || "")}${T.made ? ` · 계산 ${esc(T.made)}` : ""}</p>`;
  }

  window.Track = { view };
})();
