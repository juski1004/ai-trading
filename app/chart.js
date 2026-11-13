/* 앱 전용 주가 차트 (휴대폰용). TradingView Lightweight Charts v4.2.3 (Apache 2.0, vendor/ 에 포함).
   - 일봉 · 주봉 · 월봉 전환 (주·월봉은 일봉 data/market.json 을 묶어서 만든다)
   - 손가락 두 개로 확대·축소, 밀어서 이동, +/− 버튼, '처음으로' 버튼
   - 차트 위에 겹치는 지표: 이동평균(5·20·60) · 볼린저밴드(20, 2) · 일목균형표(전환·기준·구름)
   - 아래 칸 보조지표 (하나 골라 보기): MACD(12·26·9) · RSI(14) · 스토캐스틱(14·3·3)
     아래 칸은 위 차트와 함께 움직이고(확대·이동·손가락 위치), 고른 지표는 이 휴대폰에 기억
   - 거래량, AI 참고 목표가·손절가 선
   - 전체 화면: 화면을 꽉 채우고 (안드로이드는) 가로로 돌림. 아이폰은 휴대폰을 가로로 돌리면 가로 전체 화면
   - 손가락이 닿은 날의 시가·고가·저가·종가·등락률·거래량과 지표 값을 위에 보여 줌
   index.html 이 AppChart.html(sym) 을 넣고 AppChart.mount(sym) 을 부른다. */
(() => {
  const UP = "#e2486b", DOWN = "#3d6fe6", MA = { 5: "#e0a020", 20: "#e2486b", 60: "#16a37a" };
  const C = { bb: "#8a7cf0", bbFill: "rgba(138,124,240,.08)", tenkan: "#ef7d32", kijun: "#2f6fd6", spanA: "rgba(22,163,122,.55)", spanB: "rgba(226,72,107,.45)",
    macd: "#2f6fd6", signal: "#ef7d32", rsi: "#8a4fd8", k: "#2f6fd6", d: "#ef7d32" };
  const OVS = [["ma", "이동평균"], ["bb", "볼린저"], ["ichi", "일목"]], SUBS = [["macd", "MACD"], ["rsi", "RSI"], ["stoch", "스토캐스틱"]];
  const HELP = { macd: "MACD선이 시그널선 위로 올라서면 상승 힘, 아래로 내려가면 하락 힘으로 봐요 (참고)",
    rsi: "70 위는 많이 오른 '과열', 30 아래는 많이 내린 '침체' 구간으로 봐요 (참고)",
    stoch: "80 위는 과열, 20 아래는 침체. %K가 %D를 위로 뚫으면 반등 신호로 봐요 (참고)" };
  const KEY = "aiLab.chart.v1";
  const won = n => (n == null ? "-" : Math.round(n).toLocaleString("ko-KR"));
  const num = (n, d = 1) => (n == null ? "-" : n.toLocaleString("ko-KR", { maximumFractionDigits: d, minimumFractionDigits: d }));
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const loadOpt = () => { try { return { ov: ["ma"], sub: "macd", ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch (e) { return { ov: ["ma"], sub: "macd" }; } };
  const saveOpt = () => { try { localStorage.setItem(KEY, JSON.stringify(OPT)); } catch (e) {} };
  let OPT = loadOpt();
  let MKT = null; const mkt = () => MKT || (MKT = fetch("../data/market.json", { cache: "force-cache" }).then(r => (r.ok ? r.json() : null)).catch(() => null));
  let cur = null;

  /* ---------- 자료 ---------- */
  function daily(m, sym) {
    const s = m && m.stocks && m.stocks[sym]; if (!s) return null;
    const out = [];
    m.dates.forEach((d, i) => { if (s.c[i] == null || s.o[i] == null) return; out.push({ time: d, open: s.o[i], high: s.h[i], low: s.l[i], close: s.c[i], vol: s.v ? s.v[i] || 0 : 0 }); });
    return out;
  }
  const weekKey = d => { const t = new Date(d + "T00:00:00Z"), wd = (t.getUTCDay() + 6) % 7; t.setUTCDate(t.getUTCDate() - wd); return t.toISOString().slice(0, 10); };
  function group(bars, keyOf) {
    const out = [];
    for (const b of bars) {
      const k = keyOf(b.time), last = out[out.length - 1];
      if (last && last.k === k) { last.high = Math.max(last.high, b.high); last.low = Math.min(last.low, b.low); last.close = b.close; last.vol += b.vol; }
      else out.push({ k, time: b.time, open: b.open, high: b.high, low: b.low, close: b.close, vol: b.vol });
    }
    return out;
  }
  const frame = (bars, tf) => (tf === "W" ? group(bars, weekKey) : tf === "M" ? group(bars, d => d.slice(0, 7)) : bars);

  /* ---------- 지표 계산 (봉 개수와 같은 길이, 없는 자리는 null) ---------- */
  const smaA = (a, n) => a.map((_, i) => { if (i < n - 1) return null; let s = 0; for (let j = i - n + 1; j <= i; j++) { if (a[j] == null) return null; s += a[j]; } return s / n; });
  function emaA(a, n) {
    const k = 2 / (n + 1), out = Array(a.length).fill(null); let prev = null, seen = 0, acc = 0;
    for (let i = 0; i < a.length; i++) {
      if (a[i] == null) continue;
      if (prev == null) { acc += a[i]; seen++; if (seen === n) { prev = acc / n; out[i] = prev; } continue; }
      prev = a[i] * k + prev * (1 - k); out[i] = prev;
    }
    return out;
  }
  const hiA = (bars, n) => bars.map((_, i) => (i < n - 1 ? null : Math.max(...bars.slice(i - n + 1, i + 1).map(b => b.high))));
  const loA = (bars, n) => bars.map((_, i) => (i < n - 1 ? null : Math.min(...bars.slice(i - n + 1, i + 1).map(b => b.low))));
  function calc(bars) {
    const c = bars.map(b => b.close), I = {};
    for (const n of [5, 20, 60]) I["ma" + n] = smaA(c, n);
    const mid = smaA(c, 20);
    const sd = c.map((_, i) => { if (mid[i] == null) return null; let s = 0; for (let j = i - 19; j <= i; j++) s += (c[j] - mid[i]) ** 2; return Math.sqrt(s / 20); });
    I.bbU = mid.map((m, i) => (m == null ? null : m + 2 * sd[i])); I.bbM = mid; I.bbL = mid.map((m, i) => (m == null ? null : m - 2 * sd[i]));
    const h9 = hiA(bars, 9), l9 = loA(bars, 9), h26 = hiA(bars, 26), l26 = loA(bars, 26), h52 = hiA(bars, 52), l52 = loA(bars, 52);
    I.tenkan = h9.map((h, i) => (h == null ? null : (h + l9[i]) / 2)); I.kijun = h26.map((h, i) => (h == null ? null : (h + l26[i]) / 2));
    const a = I.tenkan.map((t, i) => (t == null || I.kijun[i] == null ? null : (t + I.kijun[i]) / 2)), b = h52.map((h, i) => (h == null ? null : (h + l52[i]) / 2));
    I.spanA = c.map((_, i) => (i >= 26 ? a[i - 26] : null)); I.spanB = c.map((_, i) => (i >= 26 ? b[i - 26] : null)); // 26칸 앞으로 그리는 구름 (자료 안쪽만)
    const e12 = emaA(c, 12), e26 = emaA(c, 26);
    I.macd = e12.map((v, i) => (v == null || e26[i] == null ? null : v - e26[i])); I.signal = emaA(I.macd, 9);
    I.hist = I.macd.map((v, i) => (v == null || I.signal[i] == null ? null : v - I.signal[i]));
    I.rsi = Array(c.length).fill(null);
    if (c.length > 14) {
      let g = 0, l = 0; for (let i = 1; i <= 14; i++) { const d = c[i] - c[i - 1]; d > 0 ? (g += d) : (l -= d); }
      g /= 14; l /= 14; I.rsi[14] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
      for (let i = 15; i < c.length; i++) { const d = c[i] - c[i - 1]; g = (g * 13 + Math.max(d, 0)) / 14; l = (l * 13 + Math.max(-d, 0)) / 14; I.rsi[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l); }
    }
    const h14 = hiA(bars, 14), l14 = loA(bars, 14), fastK = c.map((v, i) => (h14[i] == null ? null : h14[i] === l14[i] ? 50 : (v - l14[i]) / (h14[i] - l14[i]) * 100));
    I.k = smaA(fastK, 3); I.d = smaA(I.k, 3);
    return I;
  }
  const line = (bars, a) => bars.map((b, i) => (a[i] == null ? { time: b.time } : { time: b.time, value: a[i] })); // 빈 자리는 '빈 칸'으로 두어 위·아래 칸 날짜를 맞춤

  /* ---------- 화면 ---------- */
  function html(sym) {
    const chip = (k, t, on, attr) => `<button type="button" ${attr}="${k}" aria-pressed="${on}">${t}</button>`;
    return `<section class="card ac" id="acCard" data-sym="${esc(sym)}">
      <div class="ac-bar"><div class="ac-tf" role="group" aria-label="봉 단위">${[["D", "일봉"], ["W", "주봉"], ["M", "월봉"]].map(([k, t]) => chip(k, t, k === "D", "data-ac-tf")).join("")}</div>
        <div class="ac-tools"><button type="button" data-ac="out" aria-label="축소">−</button><button type="button" data-ac="in" aria-label="확대">+</button><button type="button" data-ac="fit" aria-label="전체 기간">⟲</button><button type="button" data-ac="full" aria-label="전체 화면">⛶</button></div></div>
      <div class="ac-ind" role="group" aria-label="지표">${OVS.map(([k, t]) => chip(k, t, OPT.ov.includes(k), "data-ac-ov")).join("")}<span class="ac-sep"></span>${SUBS.map(([k, t]) => chip(k, t, OPT.sub === k, "data-ac-sub")).join("")}</div>
      <div class="ac-leg" id="acLeg"></div>
      <div class="ac-box" id="acBox"><div class="ac-main" id="acMain"><p class="sub" style="padding:40px 0;text-align:center">차트를 불러오는 중…</p></div>
        <div class="ac-subwrap" id="acSubWrap"><div class="ac-leg2" id="acLeg2"></div><div class="ac-sub" id="acSub"></div></div></div>
      <p class="sub ac-hint" id="acHint"></p>
      <button type="button" class="ac-x" data-ac="exit" aria-label="전체 화면 닫기">✕ 닫기</button>
    </section>`;
  }

  function legend(i) {
    const el = document.getElementById("acLeg"), el2 = document.getElementById("acLeg2"); if (!el || !cur) return;
    const bars = cur.bars, b = bars[i], prev = bars[i - 1], I = cur.I; if (!b) return;
    const ch = prev ? (b.close / prev.close - 1) * 100 : null, c = b.close >= b.open ? "up" : "down";
    const unit = cur.tf === "W" ? "주" : cur.tf === "M" ? "개월" : "일";
    const ov = [];
    if (OPT.ov.includes("ma")) for (const n of [5, 20, 60]) if (I["ma" + n][i] != null) ov.push(`<i style="color:${MA[n]}">${n}${unit} ${won(I["ma" + n][i])}</i>`);
    if (OPT.ov.includes("bb") && I.bbU[i] != null) ov.push(`<i style="color:${C.bb}">볼린저 ${won(I.bbU[i])} / ${won(I.bbL[i])}</i>`);
    if (OPT.ov.includes("ichi") && I.tenkan[i] != null) ov.push(`<i style="color:${C.tenkan}">전환 ${won(I.tenkan[i])}</i>${I.kijun[i] != null ? `<i style="color:${C.kijun}">기준 ${won(I.kijun[i])}</i>` : ""}`);
    el.innerHTML = `<b>${esc(cur.tf === "D" ? b.time : cur.tf === "W" ? b.time + " 주" : b.time.slice(0, 7))}</b>
      <span>시 ${won(b.open)}</span><span>고 <em class="up">${won(b.high)}</em></span><span>저 <em class="down">${won(b.low)}</em></span><span>종 <em class="${c}">${won(b.close)}</em></span>
      ${ch == null ? "" : `<span class="${ch >= 0 ? "up" : "down"}">${pct(ch)}</span>`}<span>거래량 ${b.vol >= 1e4 ? Math.round(b.vol / 1e4).toLocaleString("ko-KR") + "만" : won(b.vol)}</span><div class="ac-ma">${ov.join("")}</div>`;
    if (el2) el2.innerHTML = OPT.sub === "macd" ? `<b>MACD</b> <i style="color:${C.macd}">${num(I.macd[i], 0)}</i> <i style="color:${C.signal}">시그널 ${num(I.signal[i], 0)}</i> <i>막대 ${num(I.hist[i], 0)}</i>`
      : OPT.sub === "rsi" ? `<b>RSI(14)</b> <i style="color:${C.rsi}">${num(I.rsi[i])}</i>${I.rsi[i] >= 70 ? ' <em class="up">과열</em>' : I.rsi[i] <= 30 && I.rsi[i] != null ? ' <em class="down">침체</em>' : ""}`
      : OPT.sub === "stoch" ? `<b>스토캐스틱</b> <i style="color:${C.k}">%K ${num(I.k[i])}</i> <i style="color:${C.d}">%D ${num(I.d[i])}</i>` : "";
  }

  const base = (el, extra = {}) => LightweightCharts.createChart(el, {
    autoSize: true, layout: { background: { color: "#ffffff" }, textColor: "#6b7088", fontSize: 11, fontFamily: "Pretendard, -apple-system, sans-serif" },
    grid: { vertLines: { color: "#f1f1f7" }, horzLines: { color: "#f1f1f7" } },
    rightPriceScale: { borderColor: "#e6e4f5", minimumWidth: 74 },
    timeScale: { borderColor: "#e6e4f5", rightOffset: 3, barSpacing: 8, minBarSpacing: 2 },
    crosshair: { mode: LightweightCharts.CrosshairMode.Magnet },
    localization: { locale: "ko-KR", priceFormatter: p => won(p) },
    handleScale: { pinch: true, mouseWheel: true, axisPressedMouseMove: true }, handleScroll: { horzTouchDrag: true, vertTouchDrag: false }, ...extra });
  const fix100 = () => ({ priceRange: { minValue: 0, maxValue: 100 } }); // RSI·스토캐스틱은 0~100 고정 (70/30·80/20 기준선이 늘 보이게)
  const L = (chart, color, w = 1.5, extra = {}) => chart.addLineSeries({ color, lineWidth: w, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, ...extra });

  async function mount(sym) {
    const main = document.getElementById("acMain"); if (!main || !window.LightweightCharts) return;
    const m = await mkt(), d = daily(m, sym);
    if (!document.getElementById("acMain")) return;
    if (!d || !d.length) { main.innerHTML = '<p class="empty">이 종목은 차트 자료가 없어요.</p>'; document.getElementById("acSubWrap").style.display = "none"; return; }
    main.innerHTML = "";
    if (cur) { try { cur.chart.remove(); cur.sub.remove(); } catch (e) {} }
    const chart = base(main, { rightPriceScale: { borderColor: "#e6e4f5", minimumWidth: 74, scaleMargins: { top: 0.08, bottom: 0.24 } } });
    const sub = base(document.getElementById("acSub"), { layout: { background: { color: "#ffffff" }, textColor: "#6b7088", fontSize: 11, fontFamily: "Pretendard, -apple-system, sans-serif", attributionLogo: false }, rightPriceScale: { borderColor: "#e6e4f5", minimumWidth: 74, scaleMargins: { top: 0.12, bottom: 0.08 } },
      localization: { locale: "ko-KR", priceFormatter: p => (Math.abs(p) >= 1000 ? won(p) : num(p)) } });
    const S = {
      candles: chart.addCandlestickSeries({ upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN }),
      vol: chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false }),
      ma5: L(chart, MA[5]), ma20: L(chart, MA[20]), ma60: L(chart, MA[60]),
      bbU: L(chart, C.bb, 1), bbM: L(chart, C.bb, 1, { lineStyle: 2 }), bbL: L(chart, C.bb, 1),
      tenkan: L(chart, C.tenkan, 1.2), kijun: L(chart, C.kijun, 1.2), spanA: L(chart, C.spanA, 1), spanB: L(chart, C.spanB, 1),
      hist: sub.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false }), macd: L(sub, C.macd, 1.5, { lastValueVisible: true }), signal: L(sub, C.signal, 1.2),
      rsi: L(sub, C.rsi, 1.5, { lastValueVisible: true, autoscaleInfoProvider: fix100 }), k: L(sub, C.k, 1.5, { lastValueVisible: true, autoscaleInfoProvider: fix100 }), d: L(sub, C.d, 1.2, { autoscaleInfoProvider: fix100 }),
    };
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, visible: false });
    const s = window.__SC && window.__SC.stocks[sym];
    if (s && s.target) S.candles.createPriceLine({ price: s.target, color: UP, lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: "참고 목표가" });
    if (s && s.stop) S.candles.createPriceLine({ price: s.stop, color: DOWN, lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: "참고 손절가" });
    const guide = { rsi: [70, 30], k: [80, 20] }, glines = [];
    for (const [ser, lv] of Object.entries(guide)) for (const p of lv) glines.push(S[ser].createPriceLine({ price: p, color: "#c9c6e0", lineStyle: 2, lineWidth: 1, axisLabelVisible: false }));
    cur = { chart, sub, S, sym, tf: "D", daily: d, bars: [], I: {} };

    // 위·아래 칸 함께 움직이기
    let busy = false;
    const link = (a, b) => a.timeScale().subscribeVisibleLogicalRangeChange(r => { if (busy || !r) return; busy = true; b.timeScale().setVisibleLogicalRange(r); busy = false; });
    link(chart, sub); link(sub, chart);
    const idxOf = t => { const k = cur.bars.findIndex(b => b.time === t); return k < 0 ? cur.bars.length - 1 : k; };
    const subSeries = () => (OPT.sub === "macd" ? S.macd : OPT.sub === "rsi" ? S.rsi : S.k), subVal = i => (OPT.sub === "macd" ? cur.I.macd[i] : OPT.sub === "rsi" ? cur.I.rsi[i] : cur.I.k[i]);
    chart.subscribeCrosshairMove(p => {
      if (!cur.bars.length) return; const i = p && p.time ? idxOf(p.time) : cur.bars.length - 1; legend(i);
      if (busy) return; busy = true;
      try { if (p && p.time && OPT.sub !== "none" && subVal(i) != null) sub.setCrosshairPosition(subVal(i), p.time, subSeries()); else sub.clearCrosshairPosition(); } catch (e) {}
      busy = false;
    });
    sub.subscribeCrosshairMove(p => {
      if (!cur.bars.length) return; const i = p && p.time ? idxOf(p.time) : cur.bars.length - 1; legend(i);
      if (busy) return; busy = true;
      try { if (p && p.time) chart.setCrosshairPosition(cur.bars[i].close, p.time, S.candles); else chart.clearCrosshairPosition(); } catch (e) {}
      busy = false;
    });
    setTf("D");
  }

  function apply() { // 켠 지표만 보이게
    if (!cur) return; const S = cur.S, on = k => OPT.ov.includes(k);
    for (const n of [5, 20, 60]) S["ma" + n].applyOptions({ visible: on("ma") });
    for (const k of ["bbU", "bbM", "bbL"]) S[k].applyOptions({ visible: on("bb") });
    for (const k of ["tenkan", "kijun", "spanA", "spanB"]) S[k].applyOptions({ visible: on("ichi") });
    for (const k of ["hist", "macd", "signal"]) S[k].applyOptions({ visible: OPT.sub === "macd" });
    S.rsi.applyOptions({ visible: OPT.sub === "rsi" }); S.k.applyOptions({ visible: OPT.sub === "stoch" }); S.d.applyOptions({ visible: OPT.sub === "stoch" });
    const wrap = document.getElementById("acSubWrap"), has = OPT.sub !== "none";
    if (wrap) wrap.style.display = has ? "" : "none";
    cur.chart.applyOptions({ timeScale: { visible: !has } }); // 아래 칸이 있으면 날짜는 아래 칸에만
    const hint = document.getElementById("acHint");
    if (hint) hint.textContent = (has ? HELP[OPT.sub] + " · " : "") + "두 손가락으로 확대·축소, 밀어서 지난 기간 · ⛶ 가로 전체 화면";
    document.querySelectorAll("[data-ac-ov]").forEach(b => b.setAttribute("aria-pressed", String(on(b.dataset.acOv))));
    document.querySelectorAll("[data-ac-sub]").forEach(b => b.setAttribute("aria-pressed", String(OPT.sub === b.dataset.acSub)));
    legend(cur.bars.length - 1);
  }

  function setTf(tf) {
    if (!cur) return;
    cur.tf = tf; const bars = cur.bars = frame(cur.daily, tf), I = cur.I = calc(bars), S = cur.S;
    // 주·월봉은 오르내림 폭이 커서 로그 눈금 (같은 % 변화가 같은 높이로 보이고 축이 음수로 내려가지 않음)
    cur.chart.priceScale("right").applyOptions({ mode: tf === "D" ? LightweightCharts.PriceScaleMode.Normal : LightweightCharts.PriceScaleMode.Logarithmic });
    S.candles.setData(bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
    S.vol.setData(bars.map(b => ({ time: b.time, value: b.vol, color: b.close >= b.open ? "rgba(226,72,107,.35)" : "rgba(61,111,230,.35)" })));
    for (const k of ["ma5", "ma20", "ma60", "bbU", "bbM", "bbL", "tenkan", "kijun", "spanA", "spanB", "macd", "signal", "rsi", "k", "d"]) S[k].setData(line(bars, I[k]));
    S.hist.setData(bars.map((b, i) => (I.hist[i] == null ? { time: b.time } : { time: b.time, value: I.hist[i], color: I.hist[i] >= 0 ? "rgba(226,72,107,.55)" : "rgba(61,111,230,.55)" })));
    const show = tf === "D" ? 70 : tf === "W" ? 60 : bars.length;
    cur.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - show), to: bars.length + 2 });
    document.querySelectorAll("[data-ac-tf]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.acTf === tf)));
    apply();
  }
  function zoom(f) {
    const ts = cur && cur.chart.timeScale(), r = ts && ts.getVisibleLogicalRange(); if (!r) return;
    const w = (r.to - r.from) * f, to = r.to; ts.setVisibleLogicalRange({ from: Math.max(-2, to - Math.max(8, w)), to });
  }

  /* ---------- 전체 화면 (가로) ---------- */
  async function full(on) {
    const card = document.getElementById("acCard"); if (!card) return;
    card.classList.toggle("ac-full", on); document.body.classList.toggle("ac-lock", on);
    if (on) {
      try { if (card.requestFullscreen) await card.requestFullscreen({ navigationUI: "hide" }); } catch (e) {}
      try { if (screen.orientation && screen.orientation.lock) await screen.orientation.lock("landscape"); } catch (e) {} // 안드로이드 크롬만 됨
    } else {
      try { if (screen.orientation && screen.orientation.unlock) screen.orientation.unlock(); } catch (e) {}
      try { if (document.fullscreenElement) await document.exitFullscreen(); } catch (e) {}
    }
  }
  document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement) { const c = document.getElementById("acCard"); if (c && c.classList.contains("ac-full")) { c.classList.remove("ac-full"); document.body.classList.remove("ac-lock"); } } });
  addEventListener("hashchange", () => { if (document.body.classList.contains("ac-lock")) full(false); });

  document.addEventListener("click", e => {
    const t = e.target.closest("[data-ac-tf]"); if (t) { setTf(t.dataset.acTf); return; }
    const o = e.target.closest("[data-ac-ov]");
    if (o) { const k = o.dataset.acOv; OPT.ov = OPT.ov.includes(k) ? OPT.ov.filter(x => x !== k) : [...OPT.ov, k]; saveOpt(); apply(); return; }
    const s = e.target.closest("[data-ac-sub]");
    if (s) { OPT.sub = OPT.sub === s.dataset.acSub ? "none" : s.dataset.acSub; saveOpt(); apply(); return; } // 다시 누르면 아래 칸 끄기
    const b = e.target.closest("[data-ac]"); if (!b) return;
    const a = b.dataset.ac;
    if (a === "in") zoom(0.6); else if (a === "out") zoom(1.6); else if (a === "fit") setTf(cur ? cur.tf : "D");
    else if (a === "full") full(!document.getElementById("acCard")?.classList.contains("ac-full")); else if (a === "exit") full(false);
  });

  const css = document.createElement("style");
  css.textContent = `
  .ac{padding:12px 12px 10px}
  .ac-bar{display:flex;justify-content:space-between;align-items:center;gap:8px}
  .ac-tf,.ac-tools{display:flex;gap:4px}
  .ac-tf button,.ac-tools button,.ac-ind button{border:1px solid var(--line2,#dcd8ff);background:#fff;border-radius:10px;padding:6px 10px;font:inherit;font-size:13px;font-weight:700;color:var(--muted,#6b7088);min-width:34px}
  .ac-tf button[aria-pressed=true]{background:var(--lav-d,#6c5ce7);border-color:var(--lav-d,#6c5ce7);color:#fff}
  .ac-ind{display:flex;gap:4px;margin-top:8px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}.ac-ind::-webkit-scrollbar{display:none}
  .ac-ind button{flex:none;font-size:12px;padding:4px 9px;border-radius:14px}
  .ac-ind button[aria-pressed=true]{background:var(--lav-s,#efedff);border-color:var(--lav-d,#6c5ce7);color:var(--lav-d,#6c5ce7)}
  .ac-sep{flex:none;width:1px;background:var(--line2,#dcd8ff);margin:2px 4px}
  .ac-leg{display:flex;flex-wrap:wrap;gap:2px 8px;margin:8px 2px 4px;font-size:12px;color:var(--muted,#6b7088);min-height:34px;font-variant-numeric:tabular-nums}
  .ac-leg b{color:var(--fg,#1d2033)}.ac-leg em,.ac-leg2 em{font-style:normal;font-weight:700}.ac-leg .up,.ac-leg2 .up{color:${UP}}.ac-leg .down,.ac-leg2 .down{color:${DOWN}}
  .ac-ma{width:100%;display:flex;flex-wrap:wrap;gap:2px 8px}.ac-ma i{font-style:normal;font-size:11.5px}
  .ac-box{height:400px;display:flex;flex-direction:column}
  .ac-main{flex:1;min-height:0;position:relative}
  .ac-subwrap{height:120px;flex:none;display:flex;flex-direction:column;border-top:1px solid #eceaf8}
  .ac-leg2{font-size:11.5px;color:var(--muted,#6b7088);padding:3px 2px 0;font-variant-numeric:tabular-nums}.ac-leg2 b{color:var(--fg,#1d2033)}.ac-leg2 i{font-style:normal;margin-left:6px}
  .ac-sub{flex:1;min-height:0}
  .ac-hint{margin:6px 2px 0;font-size:12px;line-height:1.5}
  .ac-x{display:none}
  .ac.ac-full{position:fixed;inset:0;z-index:95;margin:0;border-radius:0;display:flex;flex-direction:column;padding:max(8px,env(safe-area-inset-top)) max(10px,env(safe-area-inset-right)) max(8px,env(safe-area-inset-bottom)) max(10px,env(safe-area-inset-left));background:#fff}
  .ac.ac-full .ac-box{flex:1;height:auto;min-height:0}
  .ac.ac-full .ac-subwrap{height:34%}
  .ac.ac-full .ac-hint{display:none}
  .ac.ac-full .ac-x{display:block;position:absolute;right:12px;bottom:12px;z-index:3;border:0;border-radius:14px;padding:8px 14px;font:inherit;font-weight:800;background:rgba(45,42,99,.85);color:#fff}
  .ac.ac-full .ac-leg{min-height:0}
  body.ac-lock{overflow:hidden}body.ac-lock nav,body.ac-lock .top{visibility:hidden}
  @media (orientation:portrait){.ac.ac-full .ac-main::after{content:"휴대폰을 가로로 돌리면 더 넓어요";white-space:nowrap;position:absolute;left:50%;top:8px;transform:translateX(-50%);font-size:12px;color:#8a8fa6;background:rgba(255,255,255,.85);padding:4px 10px;border-radius:10px;pointer-events:none;z-index:2}}
  @media (orientation:landscape) and (max-height:500px){.ac.ac-full .ac-ind{margin-top:4px}.ac.ac-full .ac-leg{margin:4px 2px 2px}}`;
  document.head.appendChild(css);

  window.AppChart = { html, mount, _calc: calc };
})();
