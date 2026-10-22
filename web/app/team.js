/* 시작 연출 · 호칭 · 담당 팀(본부장 1명 + 직원 5명) 고르기.
   - 앱을 열 때마다 게임 타이틀이 화면 가운데로 날아와 붙는 연출(약 2초)
   - 처음 한 번: 호칭 입력 → 본부장 고르기 → 직원 5명 고르기 → 환영 인사
   - 고른 팀은 이 휴대폰에 저장되고, 알림·추천 보고·분석 의견에 그 사람들이 나온다.
   - '내 정보' 탭의 '매니저 교체'로 다시 고를 수 있다.
   다른 파일은 Team.name(agent)·Team.photo(agent)·Team.director()·Team.reporter(date)·Team.call() 을 쓴다. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const img = f => `../img/team/${f}.jpg?v=3`;
  const KEY = "aiLab.team.v1", NAME = "aiLab.call.v1";
  const load = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

  /* agent = 분석에서 맡는 자리 (JOY 시장 · OSCAR 수급·뉴스 · RAY 차트 · MILES 진입 · LLOYD 리스크 · NOVA 큰 흐름) */
  const STAFF = [
    { id: "joy", agent: "JOY", name: "윤시아", role: "시장 흐름", tag: "차분한 아침 시황 담당", look: "긴 생머리, 단정한 미소", mind: "차분하고 꼼꼼해요", trait: "오늘 시장 온도를 숫자 한 줄로 짚어 줘요." },
    { id: "oscar", agent: "OSCAR", name: "서하린", role: "수급·뉴스·실적", tag: "발 빠른 정보통", look: "밝은 갈색 웨이브, 환한 웃음", mind: "밝고 사교적이에요", trait: "외국인·기관의 돈 흐름과 새 소식을 제일 먼저 물어와요." },
    { id: "ray", agent: "RAY", name: "차유나", role: "차트 분석", tag: "신호를 놓치지 않는 눈", look: "단발, 동그란 눈", mind: "호기심 많고 집요해요", trait: "이동평균·MACD·RSI 신호를 꼼꼼히 확인해요." },
    { id: "miles", agent: "MILES", name: "민채원", role: "진입 계획", tag: "결단력 있는 플래너", look: "빨간 립, 화려한 귀걸이", mind: "자신감 있고 단호해요", trait: "'어디서 몇 주' 살지 분할 계획을 세워요." },
    { id: "lloyd", agent: "LLOYD", name: "강도윤", role: "리스크 점검", tag: "냉철한 브레이크", look: "높은 포니테일, 터틀넥", mind: "냉정하고 직설적이에요", trait: "변동성과 손절선을 지키고, 위험하면 바로 멈추자고 해요." },
    { id: "nova", agent: "NOVA", name: "한예린", role: "큰 흐름·금리", tag: "10년을 보는 전략가", look: "동그란 안경, 단정한 정장", mind: "학구적이고 신중해요", trait: "10년 주봉과 금리 사이클로 큰 그림을 그려요." },
    { id: "egen", agent: "RAY", name: "윤하진", role: "차트 분석", tag: "에겐남 · 다정한 분석가", look: "부드러운 웨이브 머리, 크림색 카디건", mind: "다정하고 섬세해요", trait: "놓치기 쉬운 작은 신호까지 조곤조곤 설명해 줘요.", male: true },
    { id: "teto", agent: "LLOYD", name: "강태오", role: "리스크 점검", tag: "테토남 · 원칙의 수비수", look: "짧은 머리, 강한 턱선, 검은 정장", mind: "직설적이고 추진력 있어요", trait: "손절 원칙은 절대 안 깨요. 버틸 이유가 없으면 바로 정리해요.", male: true },
    { id: "puppy", agent: "OSCAR", name: "서은찬", role: "수급·뉴스·실적", tag: "강아지상 · 성실한 막내", look: "동그란 눈, 앞머리, 밝은 미소", mind: "밝고 성실하고 에너지 넘쳐요", trait: "공시·뉴스를 제일 먼저 물어와서 신나게 보고해요.", male: true },
  ];
  const DIRS = [
    { id: "theo", name: "정서연", role: "본부장", tag: "따뜻하지만 단호한 리더", look: "단정한 단발, 버건디 정장", mind: "따뜻하지만 결정은 단호해요", trait: "직원 의견을 모아 비중과 현금까지 깔끔하게 정리해 줘요." },
    { id: "seunghyun", name: "백승현", role: "본부장", tag: "선한 인상의 베테랑", look: "희끗한 머리, 안경, 콧수염", mind: "온화하고 신중해요", trait: "30년 경력답게 서두르지 않는 분할 매수와 원칙을 강조해요.", male: true },
  ];
  const DEFAULT = { dir: "theo", staff: ["joy", "oscar", "ray", "miles", "lloyd"] };
  let T = load(KEY, null), CALL = load(NAME, null);

  const person = id => STAFF.find(s => s.id === id) || DIRS.find(d => d.id === id);
  const team = () => T || DEFAULT;
  function director() { return DIRS.find(d => d.id === team().dir) || DIRS[0]; }
  function members() { return team().staff.map(person).filter(Boolean); }
  /* 그 자리(agent)를 맡은 내 직원. 없으면 본부장이 직접 본다. */
  function forAgent(agent) {
    const m = members().find(s => s.agent === agent);
    return m || { ...director(), role: "본부장 직접 검토", agent };
  }
  function reporter(date) {
    const ms = members(); let h = 0; for (const c of String(date)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return ms[h % ms.length];
  }
  const call = () => CALL || "투자자님";

  /* ---------- 시작 연출 ---------- */
  function splash() {
    const el = document.createElement("div");
    el.className = "tm-splash"; el.setAttribute("aria-hidden", "true");
    el.innerHTML = `<div class="tm-burst"></div><div class="tm-title"><img src="icon-192.png" alt=""><b>AI 투자연구소</b><small>PREMIUM AI RESEARCH</small></div>`;
    document.body.appendChild(el);
    const quick = matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTimeout(() => { el.classList.add("out"); setTimeout(() => { el.remove(); onboard(); if (CALL && T) after(); }, 450); }, quick ? 600 : 2000);
  }

  /* ---------- 처음 한 번: 호칭 → 본부장 → 직원 5명 ---------- */
  let pickDir = null, pickStaff = [];
  function sheet(html) {
    let o = document.getElementById("tmSheet");
    if (!o) { o = document.createElement("div"); o.id = "tmSheet"; o.className = "tm-sheet"; o.setAttribute("role", "dialog"); o.setAttribute("aria-modal", "true"); document.body.appendChild(o); }
    o.innerHTML = `<div class="tm-box">${html}</div>`; o.scrollTop = 0;
    return o;
  }
  function closeSheet() { document.getElementById("tmSheet")?.remove(); }
  function onboard(force) {
    if (!CALL) return askName();
    if (!T || force) return chooseDir();
  }
  function askName(edit) {
    sheet(`<div class="tm-step">${edit ? "호칭 바꾸기" : "처음 오셨네요"}</div>
      <h2>어떻게 불러 드릴까요?</h2>
      <p class="sub">본부장과 직원들이 이 호칭으로 보고드려요.</p>
      <input id="tmName" maxlength="12" placeholder="예: 민준님, 김 대표님" value="${esc(CALL || "")}" autocomplete="nickname" aria-label="호칭">
      <div class="chips tm-sug">${["대표님", "사장님", "고객님", "투자자님"].map(x => `<button type="button" data-sug="${x}">${x}</button>`).join("")}</div>
      <button class="cta" type="button" data-tm="name">${edit ? "저장" : "다음"}</button>`);
    setTimeout(() => document.getElementById("tmName")?.focus(), 50);
  }
  const card = (p, on, kind) => `<button type="button" class="tm-card${on ? " on" : ""}" data-${kind}="${p.id}" aria-pressed="${on}">
      <img src="${img(p.id)}" alt="${esc(p.name)} 사진" loading="lazy">
      <span class="tm-info"><b>${esc(p.name)}</b> <span class="tm-role">${esc(p.role)}</span>
        <span class="tm-tag">${esc(p.tag)}</span>
        <span class="tm-line"><i>외모</i>${esc(p.look)}</span><span class="tm-line"><i>성격</i>${esc(p.mind)}</span><span class="tm-line"><i>특징</i>${esc(p.trait)}</span></span>
      <span class="tm-check" aria-hidden="true"></span></button>`;
  function chooseDir() {
    pickDir = pickDir || team().dir;
    sheet(`<div class="tm-step">1 / 2</div><h2>${esc(call())}, 담당 매니저를 골라주세요</h2>
      <p class="sub">먼저 모든 보고를 최종 정리해 드릴 <b>본부장</b>을 골라요.</p>
      <div class="tm-list">${DIRS.map(d => card(d, d.id === pickDir, "dir")).join("")}</div>
      <button class="cta" type="button" data-tm="dirok">다음: 직원 5명 고르기</button>`);
  }
  function chooseStaff() {
    if (!pickStaff.length) pickStaff = [...team().staff];
    const n = pickStaff.length;
    sheet(`<div class="tm-step">2 / 2</div><h2>함께할 직원 5명을 골라주세요</h2>
      <p class="sub">고른 직원이 맡은 분야를 분석해서 보고해요. 같은 분야를 두 명 골라도 되고, 비는 분야는 본부장이 직접 봐요.</p>
      <div class="tm-count"><b>${n}</b> / 5명 선택</div>
      <div class="tm-list">${STAFF.map(s => card(s, pickStaff.includes(s.id), "st")).join("")}</div>
      <button class="cta" type="button" data-tm="stok" ${n === 5 ? "" : "disabled"}>${n === 5 ? "이 팀으로 시작" : `${5 - n}명 더 골라주세요`}</button>
      <button class="cta sub2" type="button" data-tm="back">‹ 본부장 다시 고르기</button>`);
  }
  function welcome() {
    const d = director(), ms = members();
    sheet(`<div class="tm-welcome"><img src="${img(d.id)}" alt=""><p class="tm-bubble"><b>${esc(d.name)} ${esc(d.role)}</b><br>${esc(call())}, 반갑습니다. 오늘부터 제가 담당합니다.
      ${ms.map(m => esc(m.name)).join(", ")} 직원과 함께 매일 장 마감 뒤 6시에 브리핑을, 6시 10분에 추천 종목 보고를 가져오겠습니다.</p>
      <div class="tm-faces">${ms.map(m => `<img src="${img(m.id)}" alt="${esc(m.name)}" title="${esc(m.name)}">`).join("")}</div></div>
      <button class="cta" type="button" data-tm="done">시작하기</button>`);
  }

  document.addEventListener("click", e => {
    const sug = e.target.closest("[data-sug]"); if (sug) { const i = document.getElementById("tmName"); if (i) i.value = sug.dataset.sug; return; }
    const dc = e.target.closest("[data-dir]"); if (dc) { pickDir = dc.dataset.dir; chooseDir(); return; }
    const sc = e.target.closest("[data-st]");
    if (sc) {
      const id = sc.dataset.st, i = pickStaff.indexOf(id);
      if (i >= 0) pickStaff.splice(i, 1); else if (pickStaff.length < 5) pickStaff.push(id);
      const y = document.getElementById("tmSheet")?.scrollTop || 0; chooseStaff(); const o = document.getElementById("tmSheet"); if (o) o.scrollTop = y;
      return;
    }
    const b = e.target.closest("[data-tm]"); if (!b) return;
    const a = b.dataset.tm;
    if (a === "name") {
      const v = (document.getElementById("tmName")?.value || "").trim().slice(0, 12);
      if (!v) { document.getElementById("tmName")?.focus(); return; }
      CALL = v; save(NAME, v);
      if (T) { closeSheet(); refresh(); } else chooseDir();
    } else if (a === "dirok") chooseStaff();
    else if (a === "back") chooseDir();
    else if (a === "stok" && pickStaff.length === 5) { T = { dir: pickDir, staff: [...pickStaff] }; save(KEY, T); welcome(); }
    else if (a === "done") { closeSheet(); refresh(); after(); }
    else if (a === "swap") { pickDir = team().dir; pickStaff = [...team().staff]; chooseDir(); }
    else if (a === "rename") askName(true);
  });
  document.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.id === "tmName") document.querySelector('[data-tm="name"]')?.click(); });
  const refresh = () => window.dispatchEvent(new HashChangeEvent("hashchange"));
  /* 팀까지 고른 뒤: 처음이면 사용법 안내, 그다음 알림 확인 */
  function after() {
    let seen = null; try { seen = localStorage.getItem("appGuideSeen"); } catch (e) {}
    if (!seen) setTimeout(() => document.getElementById("helpBtn")?.click(), 300);
    setTimeout(() => window.Report && Report._check(), 900);
  }

  /* ---------- 내 정보 탭 ---------- */
  function meView() {
    const d = director(), ms = members();
    return `<section class="card tm-me"><div class="tm-hi"><div><div class="sub">반갑습니다</div><h2>${esc(call())}</h2></div><button class="pclink tm-sm" type="button" data-tm="rename">호칭 바꾸기</button></div></section>
    <section class="card"><div class="hd"><h2>나의 담당 팀</h2><button class="pclink tm-sm" type="button" data-tm="swap">매니저 교체</button></div>
      <div class="tm-list tm-mine">${card(d, false, "x")}${ms.map(m => card(m, false, "x")).join("")}</div></section>
    <section class="card"><div class="hd"><h2>앱처럼 쓰기</h2></div><p class="sub">아이폰: 공유 → 홈 화면에 추가 · 안드로이드: 메뉴 → 홈 화면에 추가</p></section>`;
  }

  /* 모양 */
  const css = document.createElement("style");
  css.textContent = `
  .tm-splash{position:fixed;inset:0;z-index:60;display:grid;place-items:center;background:radial-gradient(600px 400px at 50% 40%,#f3f1ff,#f6f7fb 70%);transition:opacity .45s ease}
  .tm-splash.out{opacity:0}
  .tm-title{display:flex;flex-direction:column;align-items:center;gap:10px;animation:tmSlam .9s cubic-bezier(.25,.9,.3,1) both}
  .tm-title img{width:84px;height:84px;border-radius:26px;box-shadow:0 16px 40px rgba(108,92,231,.3)}
  .tm-title b{font-size:38px;font-weight:900;letter-spacing:-1.2px;background:linear-gradient(135deg,#6c5ce7,#4a90f0);-webkit-background-clip:text;background-clip:text;color:transparent}
  .tm-title small{font-family:var(--f-disp);font-size:11px;letter-spacing:.38em;color:#a0a5b8}
  .tm-burst{position:absolute;width:240px;height:240px;border-radius:50%;border:3px solid #cdc6ff;opacity:0;animation:tmBurst .7s ease-out .55s both}
  @keyframes tmSlam{0%{transform:scale(4.2) rotate(-6deg);opacity:0;filter:blur(8px)}55%{transform:scale(.92) rotate(1deg);opacity:1;filter:blur(0)}72%{transform:scale(1.06)}85%{transform:scale(.98) translateX(-3px)}100%{transform:scale(1)}}
  @keyframes tmBurst{0%{transform:scale(.4);opacity:.9}100%{transform:scale(2.4);opacity:0}}
  .tm-sheet{position:fixed;inset:0;z-index:55;background:rgba(29,32,51,.32);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);overflow:auto;padding:max(24px,env(safe-area-inset-top)) 12px 24px}
  .tm-box{max-width:540px;margin:0 auto;background:#fff;border-radius:28px;padding:24px 18px 20px;box-shadow:0 24px 60px rgba(40,50,90,.25);animation:rise .35s ease both}
  .tm-box h2{margin:4px 0 6px;font-size:22px;font-weight:800;letter-spacing:-.6px}
  .tm-step{display:inline-block;font-family:var(--f-disp);font-size:12px;font-weight:700;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:12px;padding:3px 10px}
  #tmName{width:100%;margin-top:16px;font:inherit;font-size:18px;font-weight:700;padding:14px 16px;border-radius:16px;border:1.5px solid var(--line2,#dcd8ff);outline:none}
  #tmName:focus{box-shadow:0 0 0 4px var(--lav-s,#efedff)}
  .tm-list{display:flex;flex-direction:column;gap:10px;margin-top:16px}
  .tm-card{display:grid;grid-template-columns:82px minmax(0,1fr) 26px;gap:12px;align-items:center;text-align:left;width:100%;padding:10px;border-radius:20px;border:1.5px solid var(--line,#eceef6);background:#fff;transition:border-color .15s,background .15s}
  .tm-card img{width:82px;height:104px;border-radius:16px;object-fit:cover;object-position:50% 15%}
  .tm-card.on{border-color:#b9b2ff;background:linear-gradient(135deg,#f6f4ff,#f0f7ff);box-shadow:0 8px 20px rgba(108,92,231,.12)}
  .tm-info{display:flex;flex-direction:column;gap:2px;min-width:0}.tm-info b{font-size:17px}
  .tm-role{font-size:12px;font-weight:700;color:var(--lav-d,#6c5ce7)}
  .tm-tag{font-size:12.5px;font-weight:700;color:#e0688a;margin-bottom:3px}
  .tm-line{font-size:12.5px;color:var(--muted,#6b7088);line-height:1.45}.tm-line i{font-style:normal;font-weight:700;color:var(--fg,#1d2033);margin-right:6px}
  .tm-check{width:24px;height:24px;border-radius:50%;border:2px solid var(--line2,#dcd8ff);align-self:start;margin-top:4px}
  .tm-card.on .tm-check{background:#6c5ce7 url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 12l4 4 8-8' stroke='white' stroke-width='3' fill='none'/%3E%3C/svg%3E") center/16px no-repeat;border-color:#6c5ce7}
  .tm-mine .tm-check{display:none}.tm-mine .tm-card{grid-template-columns:70px minmax(0,1fr);cursor:default}.tm-mine img{width:70px;height:90px}
  .tm-count{position:sticky;top:-24px;z-index:2;margin:12px -18px 0;padding:10px 18px;background:rgba(255,255,255,.95);font-size:14px;color:var(--muted,#6b7088)}
  .tm-count b{font-family:var(--f-disp);font-size:20px;color:var(--lav-d,#6c5ce7)}
  .tm-box .cta[disabled]{opacity:.45}
  .tm-welcome{text-align:center}.tm-welcome>img{width:110px;height:140px;object-fit:cover;object-position:50% 12%;border-radius:22px;box-shadow:0 12px 30px rgba(40,50,90,.18)}
  .tm-bubble{text-align:left;margin:16px 0 0;padding:14px 16px;border-radius:20px;background:linear-gradient(135deg,#f6f4ff,#f0f7ff);font-size:15px;line-height:1.7}
  .tm-faces{display:flex;justify-content:center;margin-top:14px}.tm-faces img{width:46px;height:46px;border-radius:50%;object-fit:cover;object-position:50% 15%;border:3px solid #fff;margin-left:-10px;box-shadow:0 4px 10px rgba(40,50,90,.15)}
  .tm-hi{display:flex;justify-content:space-between;align-items:center;gap:10px}.tm-hi h2{font-size:22px}
  .tm-sm{margin-top:0!important;padding:8px 14px!important;font-size:13px!important}
  @media (prefers-reduced-motion:reduce){.tm-title,.tm-burst,.tm-box{animation:none}}`;
  document.head.appendChild(css);

  window.Team = { name: a => forAgent(a).name, photo: a => forAgent(a).id, person: forAgent, director, members, reporter, call, meView, open: () => onboard(true) };
  document.addEventListener("DOMContentLoaded", splash);
})();
