/* 앱 전용 주가 차트 (휴대폰용). TradingView Lightweight Charts v4.2.3 (Apache 2.0, vendor/ 에 포함).
   - 일봉 · 주봉 · 월봉 전환 (주·월봉은 일봉 data/market.json 을 묶어서 만든다)
   - 손가락 두 개로 확대·축소, 밀어서 이동, +/− 버튼, '처음으로' 버튼
   - 이동평균 5·20·60, 거래량, AI 참고 목표가·손절가 선
   - 전체 화면: 화면을 꽉 채우고 (안드로이드는) 가로로 돌림. 아이폰은 휴대폰을 가로로 돌리면 가로 전체 화면
   - 손가락이 닿은 날의 시가·고가·저가·종가·등락률·거래량을 위에 보여 줌
   index.html 이 AppChart.html(sym) 을 넣고 AppChart.mount(sym) 을 부른다. */
(() => {
  const UP = "#e2486b", DOWN = "#3d6fe6", MA = { 5: "#e0a020", 20: "#e2486b", 60: "#16a37a" };
  const won = n => (n == null ? "-" : Math.round(n).toLocaleString("ko-KR"));
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let MKT = null; const mkt = () => MKT || (MKT = fetch("../data/market.json", { cache: "force-cache" }).then(r => (r.ok ? r.json() : null)).catch(() => null));
  let cur = null; // { chart, series, sym, tf, bars }

  /* 일봉 → 주봉·월봉 */
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
      if (last && last.k === k) { last.high = Math.max(last.high, b.high); last.low = Math.min(last.low, b.low); last.close = b.close; last.vol += b.vol; last.end = b.time; }
      else out.push({ k, time: b.time, open: b.open, high: b.high, low: b.low, close: b.close, vol: b.vol, end: b.time });
    }
    return out;
  }
  const frame = (bars, tf) => (tf === "W" ? group(bars, weekKey) : tf === "M" ? group(bars, d => d.slice(0, 7)) : bars);
  const sma = (bars, n) => bars.map((b, i) => (i < n - 1 ? null : { time: b.time, value: bars.slice(i - n + 1, i + 1).reduce((a, x) => a + x.close, 0) / n })).filter(Boolean);

  function html(sym) {
    return `<section class="card ac" id="acCard" data-sym="${esc(sym)}">
      <div class="ac-bar"><div class="ac-tf" role="group" aria-label="봉 단위">${[["D", "일봉"], ["W", "주봉"], ["M", "월봉"]].map(([k, t]) => `<button type="button" data-ac-tf="${k}" aria-pressed="${k === "D"}">${t}</button>`).join("")}</div>
        <div class="ac-tools"><button type="button" data-ac="out" aria-label="축소">−</button><button type="button" data-ac="in" aria-label="확대">+</button><button type="button" data-ac="fit" aria-label="전체 기간">⟲</button><button type="button" data-ac="full" aria-label="전체 화면">⛶</button></div></div>
      <div class="ac-leg" id="acLeg"></div>
      <div class="ac-box" id="acBox"><p class="sub" style="padding:40px 0;text-align:center">차트를 불러오는 중…</p></div>
      <p class="sub ac-hint">두 손가락으로 확대·축소, 밀어서 지난 기간 보기 · ⛶ 가로 전체 화면</p>
      <button type="button" class="ac-x" data-ac="exit" aria-label="전체 화면 닫기">✕ 닫기</button>
    </section>`;
  }

  function legend(b, prev) {
    const el = document.getElementById("acLeg"); if (!el || !b) return;
    const ch = prev ? (b.close / prev.close - 1) * 100 : null, c = b.close >= b.open ? "up" : "down";
    const ma = cur ? Object.entries(cur.ma).map(([n, arr]) => { const p = arr.find(x => x.time === b.time); return p ? `<i style="color:${MA[n]}">${n}${cur.tf === "W" ? "주" : cur.tf === "M" ? "개월" : "일"} ${won(p.value)}</i>` : ""; }).join("") : "";
    el.innerHTML = `<b>${esc(cur.tf === "D" ? b.time : cur.tf === "W" ? b.time + " 주" : b.time.slice(0, 7))}</b>
      <span>시 ${won(b.open)}</span><span>고 <em class="up">${won(b.high)}</em></span><span>저 <em class="down">${won(b.low)}</em></span><span>종 <em class="${c}">${won(b.close)}</em></span>
      ${ch == null ? "" : `<span class="${ch >= 0 ? "up" : "down"}">${pct(ch)}</span>`}<span>거래량 ${b.vol >= 1e4 ? Math.round(b.vol / 1e4).toLocaleString("ko-KR") + "만" : won(b.vol)}</span><div class="ac-ma">${ma}</div>`;
  }

  async function mount(sym) {
    const box = document.getElementById("acBox"); if (!box || !window.LightweightCharts) return;
    const m = await mkt(), d = daily(m, sym);
    if (!document.getElementById("acBox")) return;
    if (!d || !d.length) { box.innerHTML = '<p class="empty">이 종목은 차트 자료가 없어요.</p>'; return; }
    box.innerHTML = "";
    if (cur && cur.chart) { try { cur.chart.remove(); } catch (e) {} }
    const chart = LightweightCharts.createChart(box, {
      autoSize: true, layout: { background: { color: "#ffffff" }, textColor: "#6b7088", fontSize: 11, fontFamily: "Pretendard, -apple-system, sans-serif" },
      grid: { vertLines: { color: "#f1f1f7" }, horzLines: { color: "#f1f1f7" } },
      rightPriceScale: { borderColor: "#e6e4f5", scaleMargins: { top: 0.08, bottom: 0.26 } },
      timeScale: { borderColor: "#e6e4f5", rightOffset: 3, barSpacing: 8, minBarSpacing: 2, fixLeftEdge: false },
      crosshair: { mode: LightweightCharts.CrosshairMode.Magnet },
      localization: { locale: "ko-KR", priceFormatter: p => won(p) },
      handleScale: { pinch: true, mouseWheel: true, axisPressedMouseMove: true }, handleScroll: { horzTouchDrag: true, vertTouchDrag: false },
    });
    const candles = chart.addCandlestickSeries({ upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, priceLineVisible: true });
    const vol = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, visible: false });
    const lines = {}; for (const n of [5, 20, 60]) lines[n] = chart.addLineSeries({ color: MA[n], lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    const s = window.__SC && window.__SC.stocks[sym];
    if (s && s.target) candles.createPriceLine({ price: s.target, color: UP, lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: "참고 목표가" });
    if (s && s.stop) candles.createPriceLine({ price: s.stop, color: DOWN, lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: "참고 손절가" });
    cur = { chart, candles, vol, lines, sym, tf: "D", daily: d, bars: [], ma: {} };
    chart.subscribeCrosshairMove(p => {
      const bars = cur.bars; if (!bars.length) return;
      let i = bars.length - 1;
      if (p && p.time) { const k = bars.findIndex(b => b.time === p.time); if (k >= 0) i = k; }
      legend(bars[i], bars[i - 1]);
    });
    setTf("D");
  }

  function setTf(tf) {
    if (!cur) return;
    cur.tf = tf; const bars = cur.bars = frame(cur.daily, tf);
    // 주·월봉은 오르내림 폭이 커서 로그 눈금 (같은 % 변화가 같은 높이로 보이고 축이 음수로 내려가지 않음)
    cur.chart.priceScale("right").applyOptions({ mode: tf === "D" ? LightweightCharts.PriceScaleMode.Normal : LightweightCharts.PriceScaleMode.Logarithmic });
    cur.candles.setData(bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
    cur.vol.setData(bars.map(b => ({ time: b.time, value: b.vol, color: b.close >= b.open ? "rgba(226,72,107,.35)" : "rgba(61,111,230,.35)" })));
    cur.ma = {}; for (const n of [5, 20, 60]) { cur.ma[n] = sma(bars, n); cur.lines[n].setData(cur.ma[n]); }
    const show = tf === "D" ? 70 : tf === "W" ? 60 : bars.length;
    cur.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, bars.length - show), to: bars.length + 2 });
    legend(bars[bars.length - 1], bars[bars.length - 2]);
    document.querySelectorAll("[data-ac-tf]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.acTf === tf)));
  }
  function zoom(f) {
    const ts = cur && cur.chart.timeScale(), r = ts && ts.getVisibleLogicalRange(); if (!r) return;
    const w = (r.to - r.from) * f, to = r.to; ts.setVisibleLogicalRange({ from: Math.max(-2, to - Math.max(8, w)), to });
  }

  /* 전체 화면 (가로) */
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
  .ac-tf button,.ac-tools button{border:1px solid var(--line2,#dcd8ff);background:#fff;border-radius:10px;padding:6px 10px;font:inherit;font-size:13px;font-weight:700;color:var(--muted,#6b7088);min-width:34px}
  .ac-tf button[aria-pressed=true]{background:var(--lav-d,#6c5ce7);border-color:var(--lav-d,#6c5ce7);color:#fff}
  .ac-leg{display:flex;flex-wrap:wrap;gap:2px 8px;margin:8px 2px 4px;font-size:12px;color:var(--muted,#6b7088);min-height:34px;font-variant-numeric:tabular-nums}
  .ac-leg b{color:var(--fg,#1d2033)}.ac-leg em{font-style:normal}.ac-leg .up{color:${UP}}.ac-leg .down{color:${DOWN}}
  .ac-ma{width:100%;display:flex;gap:8px}.ac-ma i{font-style:normal;font-size:11.5px}
  .ac-box{height:300px;position:relative}
  .ac-hint{margin:6px 2px 0;font-size:12px}
  .ac-x{display:none}
  .ac.ac-full{position:fixed;inset:0;z-index:95;margin:0;border-radius:0;display:flex;flex-direction:column;padding:max(8px,env(safe-area-inset-top)) max(10px,env(safe-area-inset-right)) max(8px,env(safe-area-inset-bottom)) max(10px,env(safe-area-inset-left));background:#fff}
  .ac.ac-full .ac-box{flex:1;height:auto;min-height:0}
  .ac.ac-full .ac-hint{display:none}
  .ac.ac-full .ac-x{display:block;position:absolute;right:12px;bottom:12px;z-index:3;border:0;border-radius:14px;padding:8px 14px;font:inherit;font-weight:800;background:rgba(45,42,99,.85);color:#fff}
  .ac.ac-full .ac-leg{min-height:0}
  body.ac-lock{overflow:hidden}body.ac-lock nav,body.ac-lock .top{visibility:hidden}
  @media (orientation:portrait){.ac.ac-full .ac-box::after{content:"휴대폰을 가로로 돌리면 더 넓어요";white-space:nowrap;position:absolute;left:50%;top:8px;transform:translateX(-50%);font-size:12px;color:#8a8fa6;background:rgba(255,255,255,.85);padding:4px 10px;border-radius:10px;pointer-events:none;z-index:2}}`;
  document.head.appendChild(css);

  window.AppChart = { html, mount };
})();
