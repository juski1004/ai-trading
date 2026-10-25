/* 앱이 닫혀 있어도 오는 알림(웹 푸시) 켜기·끄기 + 랭킹 서버와 통신.
   서버 주소는 web/app/server.json (Cloudflare 배포 작업이 자동으로 씀). 없으면 '준비 중'으로 보인다.
   - 알림: 평일 18:00 본부장 브리핑, 18:10 알파의 선택. 아이폰은 '홈 화면에 추가'한 앱에서만 된다(iOS 16.4+).
   - 랭킹: 동의한 사람만, 호칭과 수익률만 보낸다. 기기마다 무작위 번호(id)로 구분.
     월간 시즌 리그: 새내기(완주한 게임 3판 미만) · 일반. 지난 시즌 성적이 오면 Daily.seasonReward 로 배지·포인트. */
(() => {
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const load = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const RANK = "aiLab.rank.v1";

  let URLB = null, state = "loading", msg = "";
  const ready = fetch("server.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => { URLB = j && j.url; }).catch(() => {});
  const api = async (path, body) => {
    await ready; if (!URLB) throw new Error("서버 준비 중");
    const r = await fetch(URLB + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
    const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || r.status); return j;
  };
  const unb64u = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), c => c.charCodeAt(0));
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent), standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  async function refresh() {
    await ready;
    if (!URLB) state = "noserver";
    else if (!supported) state = ios && !standalone ? "ios" : "unsupported";
    else if (Notification.permission === "denied") state = "denied";
    else { const reg = await navigator.serviceWorker.ready; state = (await reg.pushManager.getSubscription()) ? "on" : "off"; }
    const box = document.getElementById("pushCard"); if (box) box.outerHTML = card();
  }
  async function enable() {
    try {
      if ((await Notification.requestPermission()) !== "granted") { msg = "알림 권한을 허용해야 받을 수 있어요."; return refresh(); }
      const reg = await navigator.serviceWorker.ready, { key } = await api("/vapid");
      const sub = (await reg.pushManager.getSubscription()) || (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: unb64u(key) }));
      await api("/subscribe", { sub: sub.toJSON() });
      await api("/test", { endpoint: sub.endpoint }).catch(() => {});
      msg = "알림을 켰어요. 확인용 알림을 하나 보냈어요.";
    } catch (e) { msg = "알림을 켜지 못했어요: " + e.message; }
    refresh();
  }
  async function disable() {
    try {
      const reg = await navigator.serviceWorker.ready, sub = await reg.pushManager.getSubscription();
      if (sub) { await api("/unsubscribe", { endpoint: sub.endpoint }).catch(() => {}); await sub.unsubscribe(); }
      msg = "알림을 껐어요.";
    } catch (e) { msg = "알림을 끄지 못했어요: " + e.message; }
    refresh();
  }

  function card() {
    const R = load(RANK, {});
    const body = {
      loading: '<p class="sub">확인 중…</p>',
      noserver: '<p class="sub">알림 서버를 준비 중이에요. 곧 켤 수 있어요.</p>',
      ios: '<p class="sub">아이폰은 Safari 공유 버튼 → <b>홈 화면에 추가</b> 한 뒤, 홈 화면의 앱으로 열면 알림을 켤 수 있어요.</p>',
      unsupported: '<p class="sub">이 브라우저는 알림을 지원하지 않아요. 크롬이나 삼성 인터넷에서 열어 주세요.</p>',
      denied: '<p class="sub">알림이 차단돼 있어요. 브라우저 설정 → 사이트 설정 → 알림에서 이 사이트를 허용해 주세요.</p>',
      off: '<button class="cta" type="button" data-push="on">알림 켜기</button>',
      on: '<p class="sub">✅ 켜져 있어요.</p><button class="cta sub2" type="button" data-push="off">알림 끄기</button>',
    }[state];
    return `<section class="card" id="pushCard"><div class="hd"><h2>앱 밖 알림</h2><span class="sub">평일 18:00 · 18:10</span></div>
      <p class="sub" style="margin:0 0 10px">앱을 닫아도 본부장 브리핑과 알파의 선택(게임)을 알려 드려요.</p>${body}
      ${msg ? `<p class="g-msg" role="status">${esc(msg)}</p>` : ""}
      <div class="hd" style="margin-top:16px"><h2>랭킹 참여</h2></div>
      <label class="g-auto"><input type="checkbox" data-rank ${R.on ? "checked" : ""}> 내 호칭과 모의투자 수익률을 월간 시즌 랭킹에 올리기</label>
      <p class="sub" style="margin:4px 0 0">매달 1일 새 시즌. 지난 시즌 1위 +500P · 3위 안 +300P · 상위 10% +200P · 참여 +50P와 시즌 배지.</p>
      <p class="sub" style="margin:4px 0 0">이름·연락처는 보내지 않아요. 언제든 끌 수 있어요.</p></section>`;
  }

  /* ---------- 랭킹 ---------- */
  const rid = () => { const R = load(RANK, {}); if (!R.id) { R.id = [...crypto.getRandomValues(new Uint8Array(12))].map(b => b.toString(36).padStart(2, "0")).join("").slice(0, 20); save(RANK, R); } return R.id; };
  const league = () => (load("aiLab.games.v1", []).length >= 3 ? "pro" : "rookie"); // 완주한 게임 3판부터 일반 리그
  const LNAME = { rookie: "새내기 리그", pro: "일반 리그" };
  function report(rec) { // 하루 한 번만 보냄 (서버 쓰기 한도 아끼기)
    const R = load(RANK, {}); if (!R.on) return Promise.resolve();
    const key = rec.date + ":" + rec.ret.toFixed(2) + ":" + league(); if (R.last === key) return Promise.resolve();
    board = null;
    return api("/rank", { id: rid(), nick: window.Team ? Team.call() : "익명", ret: rec.ret, ai: rec.ai, start: rec.start, days: rec.days, done: rec.done, league: league() })
      .then(() => { const R2 = load(RANK, {}); R2.last = key; save(RANK, R2); }).catch(() => {});
  }
  let board = null, boardAt = 0, boardL = "";
  async function getBoard(lg) {
    lg = lg || league();
    if (board && boardL === lg && Date.now() - boardAt < 60e3) return board;
    try {
      board = await api(`/rank?league=${lg}&id=` + encodeURIComponent(load(RANK, {}).id || "")); boardAt = Date.now(); boardL = lg;
      if (board.last && window.Daily && Daily.seasonReward) Daily.seasonReward(board.last); // 지난 시즌 배지·보상 (한 번만)
    } catch (e) { board = { error: e.message }; }
    return board;
  }

  document.addEventListener("click", e => {
    const b = e.target.closest("[data-push]"); if (b) { b.disabled = true; (b.dataset.push === "on" ? enable : disable)(); }
  });
  document.addEventListener("change", e => {
    if (!e.target.matches("[data-rank]")) return;
    const R = load(RANK, {}); R.on = e.target.checked; R.last = ""; save(RANK, R); if (R.on) rid();
    board = null; window.dispatchEvent(new Event("rankchange"));
  });

  window.Push = { card: () => { setTimeout(refresh, 0); return card(); }, report, getBoard, league, LNAME, rankOn: () => !!load(RANK, {}).on, id: () => load(RANK, {}).id || "" };
})();
