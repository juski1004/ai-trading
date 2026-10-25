/* 홈 '오늘의 리포트': 마감 현황 · 경제지표 · 뉴스 · 공시 · 수급 · 매집 포착 · 알파의 선택 · 종목 분석 · 거래하기 · AI 대결 을
   옆으로 쭉쭉 넘겨 보는 전문 리포트. 휴대폰은 한 장씩 밀어 넘기고, PC(넓은 화면)는 여러 장을 한눈에 본다.
   index.html 이 Deck.view(SC) 를 부르고, 데이터(outlook·why·pick·deck.json)는 여기서 한 번만 받는다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const cls = x => (x > 0 ? "up" : x < 0 ? "down" : "flat");
  const pts = s => Math.round((s + 1) / 2 * 100);
  const eok = x => `${x >= 0 ? "+" : ""}${Math.round(x).toLocaleString("ko-KR")}억`;
  const nm = a => (window.Team ? Team.name(a) : a);
  const face = a => (window.Team ? `../img/team/${Team.photo(a)}.jpg?v=4` : "");

  let D = null, asked = "";
  const get = f => fetch("../data/" + f, { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  Promise.all([get("outlook.json"), get("why.json"), get("pick.json"), get("deck.json"), get("earnings.json")]).then(([o, w, p, d, e]) => {
    D = { o, w, p, e, d: d || { eco: [], disc: [] } };
    if (!location.hash || location.hash === "#home") window.dispatchEvent(new HashChangeEvent("hashchange"));
  });

  const who = (a, role) => `<div class="dk-who"><img src="${face(a)}" alt=""><span><b>${esc(nm(a))}</b><small>${role}</small></span></div>`;
  const page = (id, title, sub, body, a, role) => `<section class="dk-page" id="dk-${id}" aria-labelledby="dk-h-${id}">
    <div class="dk-hd"><div><h2 id="dk-h-${id}">${title}</h2><p class="sub">${sub}</p></div>${a ? who(a, role) : ""}</div>${body}</section>`;
  const tone = t => `<span class="dk-tone ${t === "호재" ? "up" : t === "악재" ? "down" : "flat"}">${esc(t || "중립")}</span>`;
  // 긴 목록: n개만 보이고 나머지는 '더 보기'로 펼침
  const more = (lis, n) => lis.length <= n ? `<ul class="dk-news">${lis.join("")}</ul>` : `<ul class="dk-news">${lis.slice(0, n).join("")}</ul><details class="dk-more"><summary>더 보기 (${lis.length - n}개)</summary><ul class="dk-news">${lis.slice(n).join("")}</ul></details>`;
  const row = (sym, s, right) => `<li><button class="dk-row" type="button" data-sym="${esc(sym)}"><span class="nm">${esc(s.name)}</span>${right}</button></li>`;

  function pages(SC) {
    const S = Object.entries(SC.stocks), M = SC.market || {}, F = (D.o && D.o.facts) || {}, W = (D.w && D.w.date === SC.date && D.w.sym) || {};
    const up = S.filter(([, s]) => s.chg > 0).length, dn = S.filter(([, s]) => s.chg < 0).length;
    const byChg = [...S].sort((a, b) => b[1].chg - a[1].chg);
    const mv = ([sym, s]) => {
      const w = W[sym];
      return `<li><button class="dk-row tall" type="button" data-sym="${esc(sym)}"><span class="nm">${esc(s.name)} <b class="${cls(s.chg)}">${pct(s.chg)}</b></span>
        <span class="dk-why">${w ? `${tone(w.tone)} ${esc(w.line)}` : '<span class="flat">이유 정리 중</span>'}</span></button></li>`;
    };
    const ix = (k, lab, d) => { const x = M[k]; return x ? `<div class="dk-ix"><span>${lab}</span><b class="num">${x.v.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d })}</b><small class="num ${cls(x.chg)}">${pct(x.chg)}</small></div>` : ""; };
    const out = [];

    out.push(["close", "마감 현황", page("close", "마감 현황", `${SC.date} 장 마감`,
      `<div class="dk-ixs">${ix("kospi", "코스피", 2)}${ix("kosdaq", "코스닥", 2)}${ix("usdkrw", "원/달러", 1)}</div>
       <p class="dk-line">분석 종목 ${S.length}개 중 <b class="up">${up}개 상승</b> · <b class="down">${dn}개 하락</b></p>
       <h3>많이 오른 종목</h3><ul class="dk-list">${byChg.slice(0, 4).map(mv).join("")}</ul>
       <h3>많이 내린 종목</h3><ul class="dk-list">${byChg.slice(-4).reverse().map(mv).join("")}</ul>`, "LLOYD", "리스크 점검")]);

    const so = sym => (window.stockOf ? window.stockOf(sym) : SC.stocks[sym]), W0 = (window.getWatch ? window.getWatch() : []).filter(so);
    out.push(["watch", "관심 종목", page("watch", "관심 종목", "★로 담아 둔 종목",
      W0.length ? `<ul class="dk-list">${W0.map(sym => { const s = so(sym); return row(sym, s, `<span class="num"><b>${won(s.price)}</b> <i class="${cls(s.chg)}">${pct(s.chg)}</i>${s.score == null ? "" : ` · ${pts(s.score)}점`}</span>`); }).join("")}</ul>`
        : '<p class="empty">아직 없어요. 종목 화면 이름 옆의 ☆을 누르면 여기 모여요.</p>')]);

    const fx = (k, lab, u = "%") => F[k] == null ? "" : `<div class="dk-kv"><span>${lab}</span><b class="num ${typeof F[k] === "number" && u === "%" ? cls(F[k]) : ""}">${typeof F[k] === "number" ? (u === "%" ? pct(F[k]) : F[k].toLocaleString("ko-KR") + u) : esc(F[k])}</b></div>`;
    const K = F["코스피"] || {}, Q = F["코스닥"] || {};
    out.push(["eco", "경제지표", page("eco", "경제지표", "환율·유가·금리·공포지수",
      `<div class="dk-kvs">${fx("원달러_20일%", "원/달러 (20일)")}${fx("WTI_20일%", "국제유가 (20일)")}${fx("미국10년물", "미국 10년 금리", "%p")}${fx("VIX", "공포지수 VIX", "")}
        ${K["20일"] != null ? `<div class="dk-kv"><span>코스피 (20일)</span><b class="num ${cls(K["20일"])}">${pct(K["20일"])}</b></div>` : ""}
        ${Q["20일"] != null ? `<div class="dk-kv"><span>코스닥 (20일)</span><b class="num ${cls(Q["20일"])}">${pct(Q["20일"])}</b></div>` : ""}</div>
       ${D.o && D.o.lines ? `<h3>시황 한 줄 ${D.o.tone ? tone(D.o.tone === "긍정" ? "호재" : D.o.tone === "부정" ? "악재" : "중립") : ""}</h3><ul class="dk-bul">${D.o.lines.slice(0, 4).map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`, "JOY", "시장 흐름")]);

    out.push(["news", "뉴스", page("news", "경제 뉴스", "오늘 시장에 영향 준 기사",
      D.d.eco.length ? more(D.d.eco.map(x => `<li><a href="${esc(x.link)}" target="_blank" rel="noopener">${esc(x.title)}<small>${esc(x.src)} · ${esc((x.date || "").slice(5))}</small></a></li>`), 5) : '<p class="empty">뉴스를 불러오는 중이에요.</p>', "OSCAR", "수급·뉴스")]);

    out.push(["disc", "공시", page("disc", "공시", "최근 이틀 금융감독원 공시",
      D.d.disc.length ? more(D.d.disc.map(x => `<li><a href="${esc(x.link)}" target="_blank" rel="noopener"><b>${esc(x.name)}</b> ${esc(x.title)}<small>${esc(x.date.slice(5))} · DART</small></a></li>`), 5) : '<p class="empty">새 공시가 없거나 불러오는 중이에요.</p>', "OSCAR", "공시 확인")]);

    const mf = F["오늘_시장수급_억원"] || {}, b5 = F["대형주_수급_5일"];
    const fl = (lab, x) => x ? `<div class="dk-flow"><b>${lab}</b><span>외국인 <i class="${cls(x.frg)}">${eok(x.frg)}</i></span><span>기관 <i class="${cls(x.org)}">${eok(x.org)}</i></span><span>개인 <i class="${cls(x.ind)}">${eok(x.ind)}</i></span></div>` : "";
    out.push(["flow", "수급", page("flow", "수급", "누가 샀고 누가 팔았나 (순매수)",
      `${fl("코스피", mf.KOSPI)}${fl("코스닥", mf.KOSDAQ)}${fl("대형주 5일", b5)}` || '<p class="empty">수급 자료가 아직 없어요.</p>', "OSCAR", "수급·뉴스")]);

    const acc = S.filter(([, s]) => (s.vol_ratio || 0) >= 1.5 && Math.abs(s.chg) < 2).sort((a, b) => b[1].vol_ratio - a[1].vol_ratio).slice(0, 6);
    const hot = S.filter(([, s]) => s.vol_ratio).sort((a, b) => b[1].vol_ratio - a[1].vol_ratio).slice(0, 4);
    const accList = `<ul class="dk-list">${acc.map(([sym, s]) => row(sym, s, `<span class="num">평소의 <b>${s.vol_ratio.toFixed(1)}배</b> · <i class="${cls(s.chg)}">${pct(s.chg)}</i></span>`)).join("")}</ul>`;
    const G = (key, html, tease) => (window.Daily ? Daily.gate(key, html, tease) : html);
    out.push(["acc", "매집 포착", page("acc", "매집 포착", "주가는 조용한데 거래가 몰린 종목",
      `${acc.length ? `<p class="dk-line">오늘 <b>${acc.length}종목</b>에서 주가는 조용한데 거래가 평소보다 크게 몰렸어요.</p>${G("acc:" + SC.date, accList, accList)}` : '<p class="empty">오늘은 조용히 사 모은 흔적이 뚜렷한 종목이 없어요.</p>'}
       <h3>거래량 급증</h3><ul class="dk-list">${hot.map(([sym, s]) => row(sym, s, `<span class="num">평소의 <b>${s.vol_ratio.toFixed(1)}배</b> · <i class="${cls(s.chg)}">${pct(s.chg)}</i></span>`)).join("")}</ul>`, "RAY", "차트·거래량")]);

    const E = (D.e && D.e.items) || [];
    if (E.length) {
      const ea = E.slice(0, 6).map(e => `<li><button class="dk-row tall" type="button" data-sym="${esc(e.sym)}"><span class="nm">${esc(e.name)} <small class="sub">${+e.date.slice(5, 7)}/${+e.date.slice(8)}${e.guess ? " 경" : ""} · ${e.days}일 뒤</small></span>
        <span class="dk-why">${tone(e.tone)} ${e.eps ? `예상 EPS ${won(e.eps)}원${e.growth != null ? ` (전년 대비 ${e.growth > 0 ? "+" : ""}${Math.round(e.growth)}%)` : ""} · ` : ""}최근 5일 <i class="${cls(e.r5)}">${pct(e.r5)}</i></span></button></li>`).join("");
      out.push(["earn", "실적 발표", page("earn", "실적 발표 전 리포트", "2주 안에 실적을 발표하는 종목",
        `<ul class="dk-bul">${E.slice(0, 6).map(e => `<li><b>${esc(e.name)}</b> ${+e.date.slice(5, 7)}월 ${+e.date.slice(8)}일${e.guess ? "경" : ""}</li>`).join("")}</ul>
         <h3>증권사 예상과 최근 주가</h3>${G("earn:" + SC.date, `<ul class="dk-list">${ea}</ul>`, `<ul class="dk-list">${ea}</ul>`)}`, "OSCAR", "실적 확인")]);
    }

    const P = D.p || {}, top = [...S].sort((a, b) => b[1].score - a[1].score).slice(0, 5);
    out.push(["pick", "알파의 선택", page("pick", "알파의 선택", "알파 팀이 오늘 게임 계좌에 담은 종목 (게임·참고용)",
      `${P.found && window.Report && !Report.isOpen() ? `<div class="dk-pick"><b>18:10에 공개돼요</b><p>알파 팀이 오늘 게임 계좌에 담은 종목을 정리하고 있어요.</p>${G("early:" + P.date, "")}</div>` : P.found ? `<div class="dk-pick"><b>${esc(P.name)}</b><p>${esc(P.reason || "")}</p><a class="pclink" href="#pick">알파의 보고서 보기 ▶</a></div>` : `<p class="dk-line">${esc(P.reason || "알파의 선택 보고를 준비 중이에요.")}</p>`}
       <h3>AI 점수 상위</h3><ul class="dk-list">${top.map(([sym, s]) => row(sym, s, `<span class="num"><b>${pts(s.score)}점</b> <span class="chip ${s.label}">${s.label}</span></span>`)).join("")}</ul>`, "MILES", "진입 계획")]);

    out.push(["ask", "종목 분석", page("ask", "종목 분석", "종목을 입력하면 AI 분석팀이 답해요",
      `<form class="dk-ask" data-ask><input name="q" placeholder="예: 삼성전자, HMM, 005930" value="${esc(asked)}" autocomplete="off" aria-label="분석할 종목"><button type="submit">분석</button></form>
       <div id="dk-ans">${answer(SC, asked)}</div>`, "THEO", "종합 판단")]);

    out.push(["trade", "거래하기", page("trade", "거래하기", "가상 1,000만 원으로 시작, 실제 종가에 사고팔기",
      `<p class="dk-line">관심 종목을 고르고 매수·매도 버튼으로 바로 주문해요. 체결은 그날 실제 종가, 자동 손절 -5% · 익절 +10%.</p>
       <a class="pclink" href="#game">거래 화면 열기 ▶</a>`, "MILES", "주문 도우미")]);

    out.push(["vs", "AI 대결", page("vs", "AI 대결", "내 팀 vs 알파 팀, 수익률(%)로 겨루기",
      `${window.Versus ? Versus.summary(SC) : ""}
       <a class="pclink" href="#vs">대결 현황 보기 ▶</a>`, "THEO", "심판")]);
    return out;
  }

  function answer(SC, q) {
    q = (q || "").trim().toLowerCase();
    if (!q) return '<p class="sub">대형주 ' + Object.keys(SC.stocks).length + "종목을 분석할 수 있어요.</p>";
    const hit = Object.entries(SC.stocks).find(([, s]) => s.name.toLowerCase().includes(q) || s.code.startsWith(q));
    if (!hit) return '<p class="empty">분석 대상(대형주)에서 찾지 못했어요. 이름을 정확히 입력해 주세요.</p>';
    const [sym, s] = hit, W = (D.w && D.w.date === SC.date && D.w.sym && D.w.sym[sym]) || null;
    const ops = s.opinions.map(o => `<li><img src="${face(o.agent)}" alt=""><div><b>${esc(nm(o.agent))}</b> <span class="num ${o.score > 0 ? "up" : o.score < 0 ? "down" : "flat"}">${o.score > 0 ? "+" : ""}${Math.round(o.score * 50)}</span><p>${esc(o.summary)}</p></div></li>`).join("");
    const d = window.Team ? Team.director() : { name: "정서연", id: "theo" };
    return `<div class="dk-res"><div class="dk-res-hd"><b>${esc(s.name)}</b> <span class="num">${won(s.price)}원</span> <i class="num ${cls(s.chg)}">${pct(s.chg)}</i>
        <span class="chip ${s.label}">${s.label} ${pts(s.score)}점</span></div>
      ${W ? `<p class="dk-line">${tone(W.tone)} ${esc(W.line)}</p>` : ""}
      <ul class="dk-ops">${ops}<li><img src="../img/team/${d.id}.jpg?v=4" alt=""><div><b>${esc(d.name)} 본부장</b><p>종합 ${pts(s.score)}점(${s.label}). 참고 목표가 ${won(s.target)}원, 손절가 ${won(s.stop)}원, 리스크 ${esc(s.risk.level)}.</p></div></li></ul>
      <a class="pclink" href="#analysis/${encodeURIComponent(sym)}">자세한 분석 보기 ▶</a></div>`;
  }

  function view(SC) {
    if (!D) return `<div class="card"><div class="skel" style="width:40%"></div><div class="skel"></div><div class="skel" style="width:70%"></div></div>`;
    const P = pages(SC);
    return `<div class="dk-tabs" role="tablist">${P.map(([id, t], k) => `<button type="button" data-dk="${id}" ${k ? "" : 'aria-current="true"'}>${t}</button>`).join("")}</div>
      <div class="dk" id="dk">${P.map(p => p[2]).join("")}</div>
      <p class="sub dk-hint">옆으로 밀어서 넘겨 보세요 · 끝에서 처음으로 이어져요</p>`;
  }

  /* 넘기기·탭·종목 질문 */
  document.addEventListener("click", e => {
    const t = e.target.closest("[data-dk]"); if (t) { document.getElementById("dk-" + t.dataset.dk)?.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" }); return; }
    const m = e.target.closest("[data-dkm]"); if (m) step(+m.dataset.dkm); // 보이는 장 수만큼(PC 3장, 휴대폰 1장) 넘김, 끝에서는 처음으로
  });
  // 끝에서 다음 → 처음, 처음에서 이전 → 끝 (화살표와 손가락 밀기 모두)
  function step(dir) {
    const dk = document.getElementById("dk"); if (!dk) return;
    const max = dk.scrollWidth - dk.clientWidth, x = dk.scrollLeft;
    if (dir > 0 && x >= max - 4) dk.scrollTo({ left: 0, behavior: "smooth" });
    else if (dir < 0 && x <= 4) dk.scrollTo({ left: max, behavior: "smooth" });
    else dk.scrollBy({ left: dir * (dk.clientWidth - 20), behavior: "smooth" });
  }
  let tx = null, tl = 0;
  document.addEventListener("touchstart", e => { const dk = e.target.closest && e.target.closest("#dk"); if (dk) { tx = e.touches[0].clientX; tl = dk.scrollLeft; } }, { passive: true });
  document.addEventListener("touchend", e => {
    if (tx == null) return; const dk = document.getElementById("dk"), dx = e.changedTouches[0].clientX - tx; tx = null;
    if (!dk || Math.abs(dx) < 50) return;
    const max = dk.scrollWidth - dk.clientWidth;
    if (dx > 0 && tl <= 4) step(-1);            // 첫 장에서 오른쪽으로 밀면 마지막 장
    else if (dx < 0 && tl >= max - 4) step(1);  // 마지막 장에서 왼쪽으로 밀면 첫 장
  }, { passive: true });
  document.addEventListener("submit", e => {
    if (!e.target.matches("[data-ask]")) return; e.preventDefault();
    asked = e.target.q.value; const box = document.getElementById("dk-ans"), SC = window.__SC;
    if (box && SC) box.innerHTML = answer(SC, asked);
  });
  document.addEventListener("scroll", e => {
    const dk = e.target; if (!dk || dk.id !== "dk") return;
    const w = dk.querySelector(".dk-page")?.offsetWidth || 1, k = Math.round(dk.scrollLeft / w);
    document.querySelectorAll(".dk-tabs button").forEach((b, i) => (i === k ? b.setAttribute("aria-current", "true") : b.removeAttribute("aria-current")));
  }, true);

  const css = document.createElement("style");
  css.textContent = `
  .dk-tabs{display:flex;gap:6px;overflow-x:auto;margin:12px -16px 0;padding:2px 16px 6px;scrollbar-width:none;position:sticky;top:58px;z-index:4;background:linear-gradient(var(--bg,#f6f7fb) 80%,transparent)}
  .dk-tabs::-webkit-scrollbar{display:none}
  .dk-tabs button{flex:none;border:1px solid var(--line2,#dcd8ff);background:#fff;border-radius:20px;padding:7px 13px;font:inherit;font-size:13px;font-weight:700;color:var(--muted,#6b7088)}
  .dk-tabs button[aria-current]{background:var(--lav-d,#6c5ce7);border-color:var(--lav-d,#6c5ce7);color:#fff}
  .dk{align-items:start;display:grid;grid-auto-flow:column;grid-auto-columns:100%;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;margin:8px -16px 0;padding:4px 16px 8px;scroll-padding:0 16px;scrollbar-width:none;overscroll-behavior-x:contain}
  .dk::-webkit-scrollbar{display:none}
  .dk-page{scroll-snap-align:start;background:var(--card,#fff);border:1px solid var(--line,#eceef6);border-radius:var(--r,22px);padding:18px;box-shadow:0 8px 26px rgba(40,50,90,.06);min-width:0}/* 내용이 잘리지 않게 높이 제한 없음 */
  .dk-hd{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:12px}.dk-hd h2{margin:0;font-size:20px}
  .dk-who{display:flex;align-items:center;gap:8px;flex:none}.dk-who img{width:42px;height:42px;border-radius:50%;object-fit:cover;object-position:50% 15%}
  .dk-who span{display:flex;flex-direction:column;font-size:13px}.dk-who small{color:var(--muted,#6b7088);font-size:11px}
  .dk-page h3{font-size:14px;margin:16px 0 6px;color:var(--ink,#2d2a63)}
  .dk-ixs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.dk-ix{background:var(--lav-s,#efedff);border-radius:14px;padding:10px;display:flex;flex-direction:column}
  .dk-ix span{font-size:12px;color:var(--muted,#6b7088)}.dk-ix b{font-size:17px}.dk-ix small{font-size:12px}
  .dk-line{margin:12px 0 0;line-height:1.6}
  .dk-list,.dk-news,.dk-bul,.dk-ops{list-style:none;margin:0;padding:0}
  .dk-row{display:flex;justify-content:space-between;gap:8px;width:100%;border:0;border-bottom:1px solid var(--line,#eceef6);background:none;padding:10px 2px;font:inherit;text-align:left;cursor:pointer}
  .dk-row>*{min-width:0}.dk-page,.dk-why,.dk-news a,.dk-bul li,.dk-line{overflow-wrap:anywhere;word-break:keep-all}
  .dk-row.tall{flex-direction:column;gap:3px}.dk-row .nm{font-weight:700}.dk-why{font-size:13px;color:var(--fg,#1d2033);line-height:1.5}
  .dk-tone{display:inline-block;font-size:11.5px;font-weight:800;border-radius:8px;padding:1px 7px;margin-right:4px;background:#f3f4f8}
  .dk-tone.up{background:#ffe9ee}.dk-tone.down{background:#e8f0ff}
  .dk-kvs{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dk-kv{background:#f6f7fb;border-radius:12px;padding:10px;display:flex;flex-direction:column;gap:2px}.dk-kv span{font-size:12px;color:var(--muted,#6b7088)}.dk-kv b{font-size:16px}
  .dk-bul li{position:relative;padding:6px 0 6px 14px;line-height:1.55;font-size:14px}.dk-bul li::before{content:"";position:absolute;left:2px;top:14px;width:6px;height:6px;border-radius:50%;background:var(--lav,#b9b2ff)}
  .dk-news li a{display:block;padding:10px 0;border-bottom:1px solid var(--line,#eceef6);color:var(--fg,#1d2033);text-decoration:none;line-height:1.5;font-size:14px}.dk-news small{display:block;color:var(--muted,#6b7088);font-size:12px;margin-top:2px}
  .dk-flow{display:grid;grid-template-columns:70px 1fr 1fr 1fr;gap:6px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line,#eceef6);font-size:13px}.dk-flow i{font-style:normal;font-weight:800;display:block}
  .dk-pick{background:linear-gradient(135deg,#f6f4ff,#f0f7ff);border-radius:16px;padding:14px}.dk-pick b{font-size:18px}.dk-pick p{margin:6px 0 0;line-height:1.6}
  .dk-ask{display:flex;gap:8px}.dk-ask input{flex:1;min-width:0;font:inherit;font-size:16px;padding:12px 14px;border-radius:14px;border:1.5px solid var(--line2,#dcd8ff)}.dk-ask button{flex:none;border:0;border-radius:14px;padding:0 18px;font:inherit;font-weight:800;background:var(--gold-g);color:var(--ink,#2d2a63)}
  .dk-res{margin-top:12px}.dk-res-hd{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.dk-res-hd b{font-size:18px}.dk-res-hd i{font-style:normal}
  .dk-ops li{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--line,#eceef6)}.dk-ops img{width:38px;height:38px;border-radius:50%;object-fit:cover;object-position:50% 15%;flex:none}.dk-ops p{margin:2px 0 0;font-size:13.5px;line-height:1.5}
  .dk-hint{text-align:center;margin:6px 0 0;font-size:12px}
  .dk-more summary{list-style:none;cursor:pointer;text-align:center;padding:10px;color:var(--lav-d,#6c5ce7);font-weight:700;font-size:13.5px}.dk-more summary::-webkit-details-marker{display:none}.dk-more[open] summary{display:none}
  @media (min-width:900px){.dk{grid-auto-columns:calc((100% - 24px)/3)}.dk-page{scroll-snap-align:none}.dk-page:nth-child(3n+1){scroll-snap-align:start}.dk-tabs{top:62px}}/* PC: 세 장씩 넘어가게 *//* PC: 세 장을 한눈에 */
  @media (min-width:640px) and (max-width:899px){.dk{grid-auto-columns:calc((100% - 12px)/2)}.dk-page{scroll-snap-align:none}.dk-page:nth-child(2n+1){scroll-snap-align:start}}`;
  document.head.appendChild(css);

  window.Deck = { view };
})();
