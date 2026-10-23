/* 본부장 브리핑 알림 + 오늘의 추천 종목 보고 (앱).
   - 18:00(한국 시간) 이후, 오늘 장 마감 데이터가 있으면: "정서연 본부장이 브리핑을 가져왔습니다" 메신저 알림 (깜빡임·소리·진동)
     → 누르면 PC 화면의 브리핑(?view=brief)을 전체 화면으로 연다.
   - 18:10 이후, data/pick.json 에 추천이 있으면: 보고한 직원 이름으로 알림 → 누르면 #pick 보고서 화면.
   - 이미 본 알림은 날짜별로 이 휴대폰에 기억(localStorage).
   index.html 은 Report.view(SC)·Report.homeCard(SC) 를 부르고, 나머지는 여기서 처리한다. */
(() => {
  const won = n => Math.round(n).toLocaleString("ko-KR");
  const pct = x => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const cls = x => (x > 0 ? "up" : x < 0 ? "down" : "flat");
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const img = id => `../img/team/${id}.jpg?v=4`;
  const get = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const set = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };

  let PICK = null, DATE = null;
  fetch("../data/pick.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(d => { PICK = d; check(); }).catch(() => {});

  /* 한국 시간 */
  function kst() {
    const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })
      .formatToParts(new Date()).map(x => [x.type, x.value]));
    return { date: `${p.year}-${p.month}-${p.day}`, min: (+p.hour % 24) * 60 + +p.minute };
  }
  const BRIEF_AT = 18 * 60, PICK_AT = 18 * 60 + 10;
  const ready = () => { const t = kst(); return DATE && DATE === t.date ? t : null; };  // 오늘 장 마감 데이터가 있을 때만

  /* ---------- 알림 (메신저 말풍선) ---------- */
  let shown = null;
  function ding() {
    try {
      const A = window.AudioContext || window.webkitAudioContext; const ctx = new A();
      [[880, 0], [1318.5, 0.16]].forEach(([f, t]) => {
        const o = ctx.createOscillator(), g = ctx.createGain(); o.type = "sine"; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, ctx.currentTime + t); g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.45);
        o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.5);
      });
      if (ctx.state === "suspended") document.addEventListener("pointerdown", () => ctx.resume(), { once: true });
    } catch (e) {}
    try { navigator.vibrate && navigator.vibrate([120, 70, 120]); } catch (e) {}
  }
  function toast(kind, who, role, photo, msg) {
    if (shown === kind) return;
    document.getElementById("rpToast")?.remove();
    shown = kind;
    const el = document.createElement("button");
    el.type = "button"; el.id = "rpToast"; el.className = "rp-toast"; el.dataset.kind = kind;
    el.setAttribute("aria-live", "assertive");
    el.innerHTML = `<span class="rp-av"><img src="${img(photo)}" alt=""><i></i></span>
      <span class="rp-body"><span class="rp-who"><b>${esc(who)}</b> ${esc(role)} <em>방금</em></span><span class="rp-msg">${msg}</span></span>
      <span class="rp-open">열기</span>`;
    document.body.appendChild(el);
    ding();
    const bell = document.getElementById("rpBell"); if (bell) bell.classList.add("on");
  }
  const busy = () => document.querySelector(".tm-splash,#tmSheet");  // 시작 연출·팀 고르기 중엔 기다림
  const D = () => (window.Team ? Team.director() : { id: "theo", name: "정서연", role: "본부장" });
  const who = date => (window.Team ? Team.reporter(date) : (PICK && PICK.reporter && { id: PICK.reporter.img, name: PICK.reporter.name, role: PICK.reporter.role }));
  const call = () => (window.Team ? Team.call() : "");
  function check() {
    const t = ready(); if (!t || busy()) return;
    if (t.min >= BRIEF_AT && get("rp.brief") !== DATE) {
      const d = D();
      toast("brief", d.name, "본부장", d.id, `${esc(call())}${call() ? ", " : ""}오늘 장 마감 <b>브리핑</b>을 가져왔습니다. 지금 보고드릴까요?`);
      return;
    }
    if (PICK && PICK.found && PICK.date === DATE && t.min >= PICK_AT && get("rp.pick") !== DATE) {
      const r = who(PICK.date);
      toast("pick", r.name, r.role, r.id, `${esc(call())}${call() ? ", " : ""}${esc(D().name)} 본부장님 확인을 거친 <b>오늘의 추천 종목</b> 보고입니다 — <b>${esc(PICK.name)}</b>`);
    }
  }
  function openBriefOverlay() {
    document.querySelector(".bover")?.remove();
    const o = document.createElement("div"); o.className = "bover";
    o.innerHTML = '<iframe src="../?view=brief" title="본부장 브리핑"></iframe>'; document.body.appendChild(o);
  }
  document.addEventListener("click", e => {
    const tEl = e.target.closest("#rpToast"); if (!tEl) return;
    const kind = tEl.dataset.kind; tEl.remove(); shown = null;
    document.getElementById("rpBell")?.classList.remove("on");
    if (kind === "brief") { set("rp.brief", DATE); openBriefOverlay(); }
    else { set("rp.pick", DATE); location.hash = "pick"; }
  });
  // 브리핑을 닫으면 이어서 추천 보고 알림
  addEventListener("message", e => { if (e.origin === location.origin && (e.data || {}).type === "briefClose") setTimeout(check, 700); });
  setInterval(check, 30000);

  /* ---------- 홈 카드 ---------- */
  function homeCard(sc) {
    DATE = sc && sc.date; setTimeout(check, 400);
    const t = ready();
    if (!PICK || !t || PICK.date !== DATE) return "";
    if (t.min < PICK_AT) return `<section class="card rp-home"><div class="rp-hrow"><img src="${img(D().id)}" alt=""><div><h2>오늘의 추천 종목</h2><p class="sub">18:10에 본부장 확인을 거쳐 보고가 올라와요.</p></div></div></section>`;
    if (!PICK.found) return `<section class="card rp-home"><div class="rp-hrow"><img src="${img(D().id)}" alt=""><div><h2>오늘은 추천을 쉬어 갑니다</h2><p class="sub">${esc(PICK.reason)}</p></div></div></section>`;
    return `<section class="card rp-home"><a class="rp-hrow" href="#pick"><img src="${img(who(PICK.date).id)}" alt=""><div><h2>오늘의 추천 · ${esc(PICK.name)}</h2>
      <p class="sub">${esc(who(PICK.date).name)} 보고 · ${esc(D().name)} 본부장 최종 의견 포함 · AI 점수 ${PICK.score}점</p></div><span class="rp-go">보기</span></a></section>`;
  }

  /* ---------- 보고서 화면 ---------- */
  function spark(p) {
    const c = p.closes || []; if (c.length < 2) return "";
    const pl = p.plan, vals = [...c, pl.stop, pl.target], mx = Math.max(...vals), mn = Math.min(...vals), W = 340, H = 130;
    const X = i => i / (c.length - 1) * W, Y = v => 8 + (mx - v) / (mx - mn || 1) * (H - 16);
    const path = c.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
    const ln = (v, col, t) => `<line x1="0" x2="${W}" y1="${Y(v)}" y2="${Y(v)}" stroke="${col}" stroke-dasharray="4 4"/><text x="4" y="${Y(v) - 4}" font-size="10" fill="${col}">${t} ${won(v)}</text>`;
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="최근 6개월 주가와 매매 계획">
      <defs><linearGradient id="rpg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#b9b2ff" stop-opacity=".45"/><stop offset="1" stop-color="#b9b2ff" stop-opacity="0"/></linearGradient></defs>
      <path d="${path}L${W},${H}L0,${H}Z" fill="url(#rpg)"/>${ln(pl.target, "#ef4565", "목표")}${ln(pl.stop, "#3d7bf2", "손절")}
      <path d="${path}" fill="none" stroke="#6c5ce7" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
  }
  function view(sc) {
    DATE = sc && sc.date;
    if (!PICK) return `<div class="card"><div class="skel"></div><div class="skel" style="width:60%"></div></div>`;
    if (!PICK.found) return `<a class="back" href="#home">‹ 홈</a><section class="card rp-home"><div class="rp-hrow"><img src="${img(D().id)}" alt=""><div><h2>오늘은 추천을 쉬어 갑니다</h2><p class="sub">${esc(PICK.reason)}</p></div></div></section>`;
    const p = PICK, r = who(p.date), d = { ...p.director, ...D() }, pl = p.plan;
    const sec = (t, body) => `<section class="card"><div class="hd"><h2>${t}</h2></div>${body}</section>`;
    const ul = a => `<ul class="rp-ul">${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
    const news = p.news || {};
    return `<a class="back" href="#home">‹ 홈</a>
    <section class="card rp-head">
      <div class="rp-from"><img src="${img(r.id)}" alt="${esc(r.name)} 사진"><div><b>${esc(r.name)}</b> <span class="sub">${esc(r.role)}</span><div class="sub">${esc(p.date)} 장 마감 · 추천 종목 보고서</div></div><span class="rp-badge">보고</span></div>
      <div class="dhead" style="margin-top:14px"><div><div class="dname">${esc(p.name)}</div><div class="meta">${esc(p.code)} · ${esc(p.market)}</div></div>
        <div><div class="dprice num">${won(p.price)}</div><div class="meta num ${cls(p.chg)}" style="text-align:right">${pct(p.chg)}</div></div></div>
      ${spark(p)}
      <div class="tiles">
        <div class="tile"><div class="k">AI 종합 점수</div><div class="v num">${p.score}<small class="sub"> /100</small></div></div>
        <div class="tile"><div class="k">리스크</div><div class="v lv-${esc(p.risk)}">${esc(p.risk)}</div></div>
        <div class="tile"><div class="k">기술 점수</div><div class="v num">${p.tech_score}<small class="sub"> /5</small></div></div>
        <div class="tile"><div class="k">재무 점수</div><div class="v num">${p.fin_score ?? "-"}<small class="sub"> /5</small></div></div>
      </div>
    </section>
    ${sec("추천 이유", `<ol class="rp-ol">${p.reasons.map(x => `<li>${esc(x)}</li>`).join("")}</ol>`)}
    ${sec("매매 계획 (참고)", `<div class="kv rp-plan">
        <div><div class="k">1차 진입</div><div class="v num">${won(pl.entry)}</div></div>
        <div><div class="k">추가 매수 (−3%)</div><div class="v num">${won(pl.add)}</div></div>
        <div><div class="k">손절 (−5%)</div><div class="v num down">${won(pl.stop)}</div></div>
        <div><div class="k">1차 목표 (+10%)</div><div class="v num up">${won(pl.target)}</div></div>
        <div><div class="k">증권사 목표가</div><div class="v num">${pl.target2 ? won(pl.target2) : "-"}</div></div>
        <div><div class="k">시장 국면</div><div class="v">${esc(p.regime)}</div></div></div>`)}
    ${sec("현재 기업 상황", ul(p.company))}
    ${sec("예상 실적 (증권사)", ul(p.estimates))}
    ${sec("뉴스", (news.summary ? `<ul class="ai-sum">${news.summary.map(x => `<li>${esc(x)}</li>`).join("")}</ul><p class="sub" style="margin:6px 0 8px">AI 요약 · 느낌 ${esc(news.tone || "")}</p>` : "") +
      ((news.headlines || []).length ? `<ul class="news">${news.headlines.map(n => `<li><a href="${esc(n.link || "#")}" target="_blank" rel="noopener">${esc(n.title)}<small>${esc(n.date)} · ${esc(n.src || "")}</small></a></li>`).join("")}</ul>` : '<p class="empty">최근 소식이 없어요.</p>'))}
    ${sec("거시경제", p.macro.length ? ul(p.macro) : '<p class="empty">시황 자료가 없어요.</p>')}
    ${sec("직원 의견", `<ul class="rp-staff">${p.staff.map(s0 => { const m = window.Team ? Team.person(s0.id) : { id: s0.img, name: s0.name, role: s0.role }; const s = { ...s0, img: m.id, name: m.name, role: m.agent && m.role === "본부장 직접 검토" ? "본부장 직접 검토 · " + s0.role : s0.role }; return `<li><img src="${img(s.img)}" alt=""><div><div class="rp-sn"><b>${esc(s.name)}</b> <span class="sub">${esc(s.role)}</span>${s.score != null ? `<span class="num ${s.score > 0 ? "up" : s.score < 0 ? "down" : "flat"}">${s.score > 0 ? "+" : ""}${Math.round(s.score * 50)}</span>` : ""}</div><p>${esc(s.say)}</p></div></li>`; }).join("")}</ul>`)}
    <section class="card rp-dir">
      <div class="rp-from"><img src="${img(d.id)}" alt="본부장 사진"><div><b>${esc(d.name)} ${esc(d.role)}</b><div class="sub">최종 의견 ${d.source === "AI" ? "· AI 작성" : ""}</div></div></div>
      <p class="rp-quote">${esc(d.opinion)}</p>
    </section>
    <a class="cta" href="#game/${encodeURIComponent(p.sym)}">이 종목으로 모의투자 해 보기</a>
    <a class="cta sub2" href="#analysis/${encodeURIComponent(p.sym)}">종목 분석 자세히 보기</a>
    <p class="note">추천 종목 보고는 공개 시세·재무·뉴스·증권사 전망을 AI가 정리한 참고 정보이며 투자 권유가 아닙니다. 매일 장 마감 뒤 조건을 모두 통과한 종목이 있을 때만 1종목을 보고합니다. 투자 판단과 결과의 책임은 본인에게 있습니다.</p>`;
  }

  /* 모양 */
  const css = document.createElement("style");
  css.textContent = `
  .rp-toast{position:fixed;z-index:35;left:50%;transform:translateX(-50%);top:calc(70px + env(safe-area-inset-top));width:calc(100% - 24px);max-width:536px;display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:12px;align-items:center;text-align:left;
    background:#fff;border:1.5px solid var(--line2,#dcd8ff);border-radius:22px;padding:12px 14px;box-shadow:0 18px 44px rgba(76,64,180,.22);animation:rpIn .45s cubic-bezier(.2,1.4,.4,1) both,rpGlow 1.6s ease-in-out .45s infinite}
  .rp-av{position:relative;width:48px;height:48px}.rp-av img{width:48px;height:48px;border-radius:50%;object-fit:cover;object-position:50% 15%}
  .rp-av i{position:absolute;right:-1px;top:-1px;width:13px;height:13px;border-radius:50%;background:#ff5a78;border:2.5px solid #fff;animation:rpBlink 1s steps(2) infinite}
  .rp-who{display:block;font-size:13px;color:var(--muted,#6b7088)}.rp-who b{color:var(--fg,#1d2033);font-size:14px}.rp-who em{font-style:normal;color:var(--dim,#a0a5b8);font-size:11.5px;margin-left:4px}
  .rp-msg{display:block;font-size:14.5px;line-height:1.45;margin-top:2px;color:var(--fg,#1d2033)}
  .rp-open{font-size:12.5px;font-weight:800;color:var(--ink,#2d2a63);background:var(--gold-g,#e9e6ff);border-radius:16px;padding:7px 12px}
  @keyframes rpIn{from{opacity:0;transform:translate(-50%,-24px) scale(.96)}}
  @keyframes rpGlow{50%{box-shadow:0 18px 44px rgba(76,64,180,.22),0 0 0 6px rgba(185,178,255,.35)}}
  @keyframes rpBlink{50%{opacity:.25}}
  .rp-home .rp-hrow{display:grid;grid-template-columns:52px minmax(0,1fr) auto;gap:14px;align-items:center;color:inherit;text-decoration:none}
  .rp-home img{width:52px;height:52px;border-radius:16px;object-fit:cover;object-position:50% 12%}
  .rp-home{background:linear-gradient(135deg,#f3f1ff,#eaf4ff)!important;border-color:var(--line2,#dcd8ff)!important}
  .rp-go{font-size:12.5px;font-weight:800;color:var(--ink,#2d2a63);background:#fff;border-radius:16px;padding:7px 12px;box-shadow:0 4px 12px rgba(76,64,180,.12)}
  .rp-from{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:12px;align-items:center}
  .rp-from img{width:44px;height:44px;border-radius:50%;object-fit:cover;object-position:50% 15%;box-shadow:0 0 0 3px var(--lav-s,#efedff)}
  .rp-badge{font-size:11.5px;font-weight:800;color:#c8243f;background:#ffe3e8;border-radius:14px;padding:4px 10px}
  .rp-ol{margin:0;padding:0;list-style:none;counter-reset:r}.rp-ol li{counter-increment:r;position:relative;padding:9px 0 9px 34px;border-top:1px solid var(--line,#eceef6);font-size:14.5px}
  .rp-ol li:first-child{border-top:0}.rp-ol li::before{content:counter(r);position:absolute;left:0;top:9px;width:24px;height:24px;border-radius:50%;background:var(--lav-s,#efedff);color:var(--lav-d,#6c5ce7);font-family:var(--f-disp);font-weight:700;font-size:13px;display:grid;place-items:center}
  .rp-ul{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:7px}.rp-ul li{position:relative;padding-left:16px;font-size:14.5px}
  .rp-ul li::before{content:"";position:absolute;left:2px;top:.6em;width:7px;height:7px;border-radius:50%;background:var(--sky,#b6d8ff)}
  .rp-plan .v{font-size:15px}
  .rp-staff{list-style:none;margin:0;padding:0}.rp-staff li{display:grid;grid-template-columns:40px minmax(0,1fr);gap:12px;padding:11px 0;border-top:1px solid var(--line,#eceef6)}
  .rp-staff li:first-child{border-top:0}.rp-staff img{width:40px;height:40px;border-radius:50%;object-fit:cover;object-position:50% 15%}
  .rp-sn{display:flex;gap:6px;align-items:baseline}.rp-sn .num{margin-left:auto;font-weight:700}.rp-staff p{margin:2px 0 0;font-size:13.5px;color:var(--muted,#6b7088)}
  .rp-dir{background:linear-gradient(160deg,#fff7f3,#f3f1ff)!important;border-color:#ffd9cc!important}
  .rp-quote{margin:14px 0 0;padding:14px 16px;background:#fff;border-radius:18px;font-size:15px;line-height:1.7;position:relative;box-shadow:0 6px 18px rgba(76,64,180,.08)}
  .rp-quote::before{content:"";position:absolute;left:22px;top:-7px;width:14px;height:14px;background:#fff;transform:rotate(45deg)}
  #rpBell{position:relative;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#fff;border:1px solid var(--line,#eceef6);flex:none}
  #rpBell svg{width:18px;height:18px;stroke:var(--lav-d,#6c5ce7);fill:none;stroke-width:2}
  #rpBell.on::after{content:"";position:absolute;right:5px;top:5px;width:8px;height:8px;border-radius:50%;background:#ff5a78;animation:rpBlink 1s steps(2) infinite}
  @media (prefers-reduced-motion:reduce){.rp-toast,.rp-av i,#rpBell.on::after{animation:none}}`;
  document.head.appendChild(css);

  // 머리글 종: 누르면 지금 받을 수 있는 보고를 다시 띄움
  document.addEventListener("DOMContentLoaded", () => {
    const top = document.querySelector(".top"), help = document.getElementById("helpBtn");
    if (!top || document.getElementById("rpBell")) return;
    const b = document.createElement("button"); b.type = "button"; b.id = "rpBell"; b.setAttribute("aria-label", "알림");
    b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>';
    b.onclick = () => {
      const t = ready(); shown = null;
      if (t && t.min >= BRIEF_AT && get("rp.brief") !== DATE) return check();
      if (PICK && PICK.found && t && t.min >= PICK_AT) { location.hash = "pick"; return; }
      if (t && t.min >= BRIEF_AT) { openBriefOverlay(); return; }
      alert("오늘 알림은 장 마감 뒤 18:00(브리핑)과 18:10(추천 종목)에 와요.");
    };
    top.insertBefore(b, help);
  });

  window.Report = { view, homeCard, _check: check };
})();
