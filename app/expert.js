/* 전문가 기법 점검 (종목 화면) — 2026-11-24 사용자: "주식 전문가들이 쓰는 기법이든 투자 방법이든 도움이 될 만한 건 넣어 줘"
   data/market.json (일봉 약 1년치)으로 휴대폰에서 바로 계산한다. 모두 공개된 교과서 기법이고 참고용이다.
   - 미너비니 추세 템플릿 (마크 미너비니, 'Trade Like a Stock Market Wizard'): 상승 2단계 종목만 고르는 8가지 조건
   - 와인스타인 단계 분석 (스탠 와인스타인): 30주 이동평균선의 기울기와 가격 위치로 1(바닥)~4(하락) 단계
   - 상대강도 (윌리엄 오닐 CAN SLIM 의 L): 3·6개월 수익률을 코스피와 비교
   - ATR 손절 (변동성 기반, 터틀·반 타프): 평소 하루 흔들림의 2배 아래를 손절로 — 고정 -5%와 비교
   - 손익비 (리스크 관리 기본): 목표까지 이익 ÷ 손절까지 손실, 2 이상이 권장
   - 거래량 돌파 (오닐·미너비니 공통): 20일 신고가 + 평소 거래량 1.5배 이상
   - 포지션 크기 (2% 규칙): 손절에 걸려도 전체 자금의 2%만 잃게 살 금액
   index.html 이 Expert.card(sym) 를 부른다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n || 0).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(1) + "%";
  let M = null, tried = false;
  function load() {
    if (tried) return; tried = true;
    fetch("../data/market.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => { M = d || {}; dispatchEvent(new HashChangeEvent("hashchange")); })
      .catch(() => { M = {}; });
  }
  const sma = (a, n, end = a.length) => { if (end < n) return null; let s = 0; for (let i = end - n; i < end; i++) s += a[i]; return s / n; };
  const ret = (a, n) => (a.length > n ? (a[a.length - 1] / a[a.length - 1 - n] - 1) * 100 : null);

  function calc(st, idx) {
    const c = st.c, h = st.h, l = st.l, v = st.v, n = c.length, px = c[n - 1];
    const ma50 = sma(c, 50), ma150 = sma(c, 150), ma200 = sma(c, 200), ma200p = sma(c, 200, n - 20);
    const y = Math.min(n, 250), hi52 = Math.max(...h.slice(n - y)), lo52 = Math.min(...l.slice(n - y));
    const rs6 = ret(c, 126), rs3 = ret(c, 63), k6 = idx ? ret(idx, 126) : null, k3 = idx ? ret(idx, 63) : null;
    const tmpl = [
      ["주가 > 150일·200일선", ma150 && ma200 && px > ma150 && px > ma200],
      ["150일선 > 200일선", ma150 && ma200 && ma150 > ma200],
      ["200일선이 한 달째 오르는 중", ma200 && ma200p && ma200 > ma200p],
      ["50일선 > 150일·200일선", ma50 && ma150 && ma200 && ma50 > ma150 && ma50 > ma200],
      ["주가 > 50일선", ma50 && px > ma50],
      ["52주 최저가보다 30% 이상 위", px >= lo52 * 1.3],
      ["52주 최고가에서 25% 안쪽", px >= hi52 * 0.75],
      ["코스피보다 강함 (6개월)", rs6 != null && k6 != null && rs6 > k6],
    ];
    // 와인스타인: 30주 ≈ 150거래일
    const w30 = ma150, w30p = sma(c, 150, n - 25);
    const slope = w30 && w30p ? (w30 / w30p - 1) * 100 : 0;
    const stage = !w30 ? null : px > w30 && slope > 0.5 ? 2 : px < w30 && slope < -0.5 ? 4 : px >= w30 ? 3 : 1;
    // ATR(14)
    let tr = 0; for (let i = n - 14; i < n; i++) tr += Math.max(h[i] - l[i], Math.abs(h[i] - c[i - 1]), Math.abs(l[i] - c[i - 1]));
    const atr = tr / 14, atrStop = px - 2 * atr;
    const vol20 = sma(v, 20, n - 1), hi20 = Math.max(...h.slice(n - 21, n - 1));
    const breakout = px > hi20 && v[n - 1] >= vol20 * 1.5;
    return { px, tmpl, pass: tmpl.filter(x => x[1]).length, stage, slope, rs6, rs3, k6, k3, atr, atrStop, breakout, hi52, lo52, vr: vol20 ? v[n - 1] / vol20 : null };
  }

  const STAGE = { 1: ["1단계 · 바닥 다지기", "옆으로 기며 힘을 모으는 구간. 아직 살 때는 아님", "flat"],
    2: ["2단계 · 상승", "와인스타인이 '사는 구간'으로 꼽는 단계", "up"],
    3: ["3단계 · 꼭대기", "오름세가 꺾이며 옆으로. 새로 사기보다 정리를 생각할 구간", "flat"],
    4: ["4단계 · 하락", "30주선 아래로 내려가는 중. 사지 않는 구간", "down"] };

  function card(sym, s) {
    load();
    if (!M) return `<section class="card"><h2>전문가 기법 점검</h2><div class="skel"></div></section>`;
    const st = (M.stocks || {})[sym]; if (!st || st.c.length < 210) return "";
    const R = calc(st, (M.index || {}).c), S = R.stage && STAGE[R.stage];
    const tgt = s && s.target, stop = s && s.stop, rr = tgt && stop && R.px > stop ? (tgt - R.px) / (R.px - stop) : null;
    const risk = stop ? (R.px - stop) / R.px : 0.05, size = 0.02 / risk * 100; // 2% 규칙: 자금의 몇 %까지 살지
    const ok = b => (b ? "✅" : "▫️");
    return `<section class="card ex">
      <h2>전문가 기법 점검</h2><p class="sub">유명 투자자들의 공개된 기법으로 이 종목을 따져 봤어요 (참고용)</p>
      <div class="ex-b"><div class="ex-h"><b>미너비니 추세 템플릿</b><span class="${R.pass >= 7 ? "up" : R.pass <= 3 ? "down" : "flat"}"><b>${R.pass}</b>/8</span></div>
        <p class="sub">8개를 모두 채운 '상승 2단계' 종목만 사는 방식이에요. ${R.pass === 8 ? "모두 통과했어요." : R.pass >= 6 ? "거의 통과했어요." : "아직 조건이 부족해요."}</p>
        <ul class="ex-l">${R.tmpl.map(([t, b]) => `<li>${ok(b)} ${t}</li>`).join("")}</ul></div>
      ${S ? `<div class="ex-b"><div class="ex-h"><b>와인스타인 단계</b><span class="${S[2]}">${S[0]}</span></div><p class="sub">${S[1]} · 30주선 기울기 ${pct(R.slope)}</p></div>` : ""}
      <div class="ex-b"><div class="ex-h"><b>상대강도 (코스피 대비)</b><span class="${R.rs6 != null && R.k6 != null && R.rs6 > R.k6 ? "up" : "down"}">${R.rs6 != null && R.k6 != null ? (R.rs6 > R.k6 ? "시장보다 강함" : "시장보다 약함") : "-"}</span></div>
        <p class="sub">3개월 ${R.rs3 == null ? "-" : pct(R.rs3)} (코스피 ${R.k3 == null ? "-" : pct(R.k3)}) · 6개월 ${R.rs6 == null ? "-" : pct(R.rs6)} (코스피 ${R.k6 == null ? "-" : pct(R.k6)}). 오닐은 시장보다 강한 주도주만 고르라고 해요.</p></div>
      <div class="ex-b"><div class="ex-h"><b>손절 자리 (ATR 2배)</b><span>${won(R.atrStop)}원</span></div>
        <p class="sub">하루 평균 흔들림 ${won(R.atr)}원(${(R.atr / R.px * 100).toFixed(1)}%)의 2배 아래예요. 고정 손절 -5%(${won(R.px * 0.95)}원)보다 ${R.atrStop < R.px * 0.95 ? "넓어요 → 평소 흔들림만으로도 -5%에 걸릴 수 있는 종목" : "좁아요 → -5% 손절이 넉넉한 종목"}.</p></div>
      ${rr != null ? `<div class="ex-b"><div class="ex-h"><b>손익비</b><span class="${rr >= 2 ? "up" : rr < 1.5 ? "down" : "flat"}">${rr.toFixed(1)} : 1</span></div>
        <p class="sub">참고 목표가까지 이익 ÷ 참고 손절가까지 손실. 2 : 1 이상이면 세 번 중 한 번만 맞아도 본전이에요.</p></div>` : ""}
      <div class="ex-b"><div class="ex-h"><b>거래량 돌파</b><span class="${R.breakout ? "up" : "flat"}">${R.breakout ? "오늘 돌파" : "아님"}</span></div>
        <p class="sub">20일 신고가와 함께 거래량이 평소의 1.5배 이상일 때를 '진짜 돌파'로 봐요. 오늘 거래량은 평소의 ${R.vr == null ? "-" : R.vr.toFixed(1)}배예요.</p></div>
      <div class="ex-b"><div class="ex-h"><b>얼마나 살까 (2% 규칙)</b><span>자금의 ${Math.min(100, size).toFixed(0)}%까지</span></div>
        <p class="sub">손절에 걸려도 전체 자금의 2%만 잃게 사는 방법이에요. 1천만 원이면 최대 ${won(Math.min(1, size / 100) * 1e7)}원어치 (손절 ${(risk * 100).toFixed(1)}% 기준).</p></div>
      <style>.ex-b{border-top:1px solid var(--line);padding:11px 0}.ex-b:first-of-type{margin-top:8px}.ex-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:14.5px}
        .ex-h span{font-weight:700;font-size:13.5px;text-align:right}.ex-l{list-style:none;padding:0;margin:6px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:3px 8px;font-size:12.5px}</style>
    </section>`;
  }

  window.Expert = { card, calc };
})();
