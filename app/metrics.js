/* 사용 집계: 서버에 날짜별 '숫자'만 보낸다 (기기 id·개인 정보 없음).
   - 하루 한 번: open(오늘 연 기기), 처음이면 new, 홈 화면 앱으로 처음 열면 install, 첫 방문 3·7일째 이후 다시 오면 d3·d7
   - 처음 한 번: tour(튜토리얼 완료), trade(첫 주문)
   - 들어온 경로: 링크의 ?from=insta|reel|dm|card|archive, 초대 링크 ?ref= → invite, 인스타 앱 안 브라우저 → insta
   저장: aiLab.m.v1 {first, src, sent:{이벤트:날짜}} */
(() => {
  const KEY = "aiLab.m.v1", SRC = ["insta", "reel", "dm", "card", "invite", "archive", "direct"];
  const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  const M = load(), q = new URLSearchParams(location.search), t = today();

  function source() {
    const f = (q.get("from") || q.get("utm_source") || "").toLowerCase();
    if (SRC.includes(f)) return f;
    if (/instagram/.test(f)) return "insta";
    if (q.get("ref")) return "invite";
    if (/Instagram/.test(navigator.userAgent) || /instagram\.com/.test(document.referrer)) return "insta";
    return "direct";
  }
  const isNew = !M.first;
  if (isNew) { M.first = t; M.src = source(); }
  const now = source(), src = now !== "direct" ? now : M.src || "direct";
  M.sent = M.sent || {};

  const server = fetch("server.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => j && j.url).catch(() => null);
  async function send(evs) {
    const u = await server; if (!u || !evs.length) return false;
    try {
      const r = await fetch(u + "/hit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ev: evs, src }), keepalive: true });
      return r.ok;
    } catch (e) { return false; }
  }
  // once: 처음 한 번만 / daily: 하루 한 번
  function mark(evs) { evs.forEach(e => (M.sent[e] = t)); save(M); }
  function ev(name) { if (M.sent[name]) return; mark([name]); send([name]); }

  const days = Math.round((Date.parse(t) - Date.parse(M.first)) / 86400e3);
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const evs = [];
  if (M.sent.open !== t) evs.push("open");
  if (isNew) evs.push("new");
  if (standalone && !M.sent.install) evs.push("install");
  if (days >= 2 && !M.sent.d3) evs.push("d3");
  if (days >= 6 && !M.sent.d7) evs.push("d7");
  if (evs.length) { mark(evs); send(evs); } else save(M);

  addEventListener("aiLab:trade", () => { if (!document.body.classList.contains("tour-on")) ev("trade"); }); // 튜토리얼 연습 주문은 빼고
  addEventListener("aiLab:tourDone", () => ev("tour"));
  addEventListener("aiLab:pushOn", () => ev("push"));

  window.Metrics = { src: () => src, social: () => ["insta", "reel", "dm"].includes(src), ev };
})();
