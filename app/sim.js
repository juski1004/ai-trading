/* 사기 전에 1만 번 돌려 보기 (2026-10-29 사용자가 보낸 릴스 '주식 사기 전 1만 번' 참고)
   최근 6개월 하루 등락률을 무작위로 다시 뽑아 앞으로 20거래일을 1만 번 그려 보고,
   게임 규칙(익절 +10% · 손절 −5%) 중 어느 쪽에 먼저 닿는지 셈. 과거 움직임 기준 참고치이며 투자 권유가 아님. */
(() => {
  const N = 10000, DAYS = 20, TAKE = 0.10, STOP = -0.05;
  const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  function run(closes) {
    const r = []; for (let i = 1; i < closes.length; i++) if (closes[i - 1] > 0) r.push(closes[i] / closes[i - 1]);
    if (r.length < 40) return null;
    let win = 0, lose = 0; const paths = [];
    for (let k = 0; k < N; k++) {
      let p = 1, hit = 0; const keep = k < 80 ? [1] : null;
      for (let d = 0; d < DAYS; d++) {
        p *= r[(Math.random() * r.length) | 0]; if (keep) keep.push(p);
        if (!hit && p - 1 >= TAKE) hit = 1; else if (!hit && p - 1 <= STOP) hit = -1;
        if (hit && !keep) break;
      }
      if (hit > 0) win++; else if (hit < 0) lose++;
      if (keep) paths.push({ v: keep, hit });
    }
    return { win: win / N, lose: lose / N, none: (N - win - lose) / N, paths };
  }
  function card(sym) {
    const s = window.__SC && __SC.stocks[sym]; if (!s || !s.closes || s.closes.length < 41) return "";
    return `<section class="card sim-card" data-sim="${esc(sym)}"><div class="hd"><div><h2>사기 전에 1만 번 돌려 보기</h2>
      <p class="sub">최근 6개월 움직임으로 앞으로 20거래일을 1만 번 그려서, 게임 규칙 <b class="up">익절 +10%</b>와 <b class="down">손절 −5%</b> 중 어디에 먼저 닿는지 세요.</p></div></div>
      <canvas class="sim-cv" width="640" height="220" aria-label="1만 번 시뮬레이션 그래프"></canvas>
      <div class="sim-out"><button class="cta" type="button" data-simgo="${esc(sym)}">1만 번 돌려 보기</button></div>
      <p class="sub" style="margin-top:6px">과거 움직임을 섞어 다시 그린 참고치예요. 앞으로도 그렇게 움직인다는 뜻은 아니며 투자 권유가 아니에요.</p></section>`;
  }
  function draw(cv, res, upto) {
    const g = cv.getContext("2d"), W = cv.width, H = cv.height, lo = 0.85, hi = 1.15, Y = v => H - ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * H;
    g.clearRect(0, 0, W, H);
    const line = (v, c) => { g.strokeStyle = c; g.setLineDash([6, 6]); g.beginPath(); g.moveTo(0, Y(v)); g.lineTo(W, Y(v)); g.stroke(); g.setLineDash([]); };
    line(1 + TAKE, "#ef4565"); line(1 + STOP, "#3d7bf2"); line(1, "#a0a5b8");
    res.paths.slice(0, upto).forEach(p => { g.strokeStyle = p.hit > 0 ? "rgba(239,69,101,.35)" : p.hit < 0 ? "rgba(61,123,242,.35)" : "rgba(160,165,184,.35)"; g.beginPath(); p.v.forEach((v, i) => { const x = (i / DAYS) * W; i ? g.lineTo(x, Y(v)) : g.moveTo(x, Y(v)); }); g.stroke(); });
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-simgo]"); if (!b) return;
    const sym = b.dataset.simgo, s = __SC.stocks[sym], box = b.closest(".sim-card"), out = box.querySelector(".sim-out"), cv = box.querySelector(".sim-cv");
    const res = run(s.closes); if (!res) { out.innerHTML = '<p class="sub">자료가 부족해요.</p>'; return; }
    const t0 = performance.now(), dur = 1600, reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const step = now => {
      const f = reduce ? 1 : Math.min(1, (now - t0) / dur);
      draw(cv, res, Math.ceil(res.paths.length * f));
      out.innerHTML = `<div class="sim-n num">${Math.round(N * f).toLocaleString("ko-KR")}<small>번 돌려 봄</small></div>`;
      if (f < 1) return requestAnimationFrame(step);
      const w = Math.round(res.win * 100), l = Math.round(res.lose * 100), n = 100 - w - l, edge = res.win / Math.max(0.01, res.win + res.lose);
      // 손절(−5%)이 익절(+10%)보다 가까워서, 아무 방향 없이 움직이면 익절 쪽이 약 33%가 평균
      const tag = edge >= 0.45 ? ["평균보다 유리한 편", "up"] : edge >= 0.28 ? ["평균 수준 (동전 던지기)", "flat"] : ["평균보다 불리한 편", "down"];
      out.innerHTML = `<div class="sim-res"><div><b class="up num">${w}%</b><small>익절 +10% 먼저</small></div><div><b class="down num">${l}%</b><small>손절 −5% 먼저</small></div><div><b class="num">${n}%</b><small>20일 안에 둘 다 아님</small></div></div>
        <p class="sim-tag ${tag[1]}">${esc(s.name)}: 과거 움직임으로 보면 <b>${tag[0]}</b>이에요 <br><small>익절 쪽 ${Math.round(edge * 100)} : 손절 쪽 ${100 - Math.round(edge * 100)} · 손절이 더 가까워서 평균은 33 : 67</small></p>
        <button class="cta sub2" type="button" data-simgo="${esc(sym)}">다시 돌려 보기</button>`;
    };
    requestAnimationFrame(step);
  });
  const css = document.createElement("style");
  css.textContent = `.sim-cv{width:100%;height:auto;aspect-ratio:640/220;margin-top:10px;border-radius:12px;background:var(--soft)}
  .sim-out{margin-top:10px;display:grid;gap:8px}.sim-n{font-size:28px;font-weight:800;text-align:center}.sim-n small{font-size:13px;margin-left:4px;color:var(--muted)}
  .sim-res{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;text-align:center}.sim-res div{background:var(--soft);border-radius:12px;padding:10px 4px;display:grid}
  .sim-res b{font-size:22px}.sim-res small{font-size:11.5px;color:var(--muted)}.sim-tag{margin:0;font-size:14px;text-align:center}`;
  document.head.appendChild(css);
  window.Sim = { card, run };
})();
