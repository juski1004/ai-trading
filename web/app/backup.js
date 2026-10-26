/* 기록 백업·복구: 이 기기의 기록(호칭·팀·튜토리얼·모의투자·예약 주문·포인트 등)을 서버에 자동으로 맡겨 두고,
   브라우저가 저장 공간을 지워도 '복구 코드' 12자리로 그대로 되살린다. 다른 기기에서 이어 하기에도 쓴다.
   - 팀을 고른 뒤부터 백업. 바뀐 게 있을 때만, 최소 2분 간격 + 화면을 떠날 때.
   - 튜토리얼 연습 중(aiLab.tour.snap.v1 있음)엔 연습 주문이 섞이니 백업하지 않음.
   저장: aiLab.bk.v1 {code, h(마지막 백업 내용 지문), at} */
(() => {
  const CK = "aiLab.bk.v1", SNAP = "aiLab.tour.snap.v1", GAP = 120e3;
  const server = fetch("server.json", { cache: "no-cache" }).then(r => (r.ok ? r.json() : null)).then(j => j && j.url).catch(() => null);
  const ls = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
  const meta = () => { try { return JSON.parse(ls.get(CK)) || {}; } catch (e) { return {}; } };
  const setMeta = m => ls.set(CK, JSON.stringify(m));
  const mine = k => (k.startsWith("aiLab.") || k === "appGuideSeen" || k === "arenaLive.v1") && k !== CK && k !== SNAP;
  function dump() {
    const o = {}; try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (mine(k)) o[k] = localStorage.getItem(k); } } catch (e) {}
    return JSON.stringify(o, Object.keys(o).sort());
  }
  const hash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = (h * 33 + s.charCodeAt(i)) >>> 0; return h.toString(36) + s.length; };
  const AB = "abcdefghjkmnpqrstuvwxyz23456789"; // 헷갈리는 글자(0·o·1·l·i) 뺌
  function newCode() { const r = new Uint8Array(12); crypto.getRandomValues(r); return [...r].map(x => AB[x % AB.length]).join(""); }
  const norm = s => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const fmt = c => (c || "").replace(/(.{4})(?=.)/g, "$1-");
  const ready = () => !!ls.get("aiLab.team.v1") && !ls.get(SNAP);

  let last = 0, busy = false;
  async function push(force) {
    if (busy || !ready()) return false;
    const m = meta(), data = dump(), h = hash(data);
    if (!force && (m.h === h || Date.now() - last < GAP)) return false;
    const u = await server; if (!u) return false;
    const first = !m.code; if (first) m.code = newCode();
    busy = true; last = Date.now();
    try {
      const r = await fetch(u + "/backup", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: m.code, data }), keepalive: data.length < 60000 });
      if (!r.ok) return false;
      m.h = h; m.at = Date.now(); setMeta(m);
      if (first) toast(`기록 자동 백업을 켰어요. 복구 코드 <b>${fmt(m.code)}</b> — 기록이 지워져도 이 코드로 되살려요. (내 정보에서 다시 볼 수 있어요)`);
      return true;
    } catch (e) { return false; } finally { busy = false; }
  }
  async function restore(input) {
    const code = norm(input);
    if (code.length !== 12) { alert("복구 코드 12자리를 확인해 주세요. (예: abcd-efgh-jkmn)"); return; }
    const u = await server; if (!u) { alert("서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요."); return; }
    let rec = null;
    try { const r = await fetch(u + "/backup?code=" + code, { cache: "no-store" }); if (r.status === 404) { alert("이 코드로 저장된 기록이 없어요."); return; } rec = await r.json(); } catch (e) {}
    if (!rec || !rec.data) { alert("서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요."); return; }
    const when = new Date(rec.at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    let o; try { o = JSON.parse(rec.data); } catch (e) { alert("백업을 읽지 못했어요."); return; }
    const J = k => { try { return JSON.parse(o[k]); } catch (e) { return null; } };
    const g = J("aiLab.game.v1"), pts = J("aiLab.pts.v1"), tm = J("aiLab.team.v1");
    const what = [tm ? "담당 팀 ✓" : "담당 팀 없음",
      g ? `모의투자 게임 ✓ (보유 ${Object.keys(g.pos || {}).length}종목 · 거래 ${(g.trades || []).length}회 · 미체결 ${(g.orders || []).length}건)` : "모의투자 게임 없음",
      J("aiLab.tour.v1")?.done ? "튜토리얼 완료 ✓" : "튜토리얼 기록 없음",
      pts && typeof pts.pts === "number" ? `포인트 ${pts.pts}P` : ""].filter(Boolean).join("\n· ");
    if (!confirm(`${when}에 백업한 기록이에요.\n· ${what}\n\n이 기록으로 바꿀까요? 지금 이 화면의 기록은 덮어써져요.`)) return;
    try { const ks = []; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (mine(k)) ks.push(k); } ks.forEach(k => localStorage.removeItem(k)); localStorage.removeItem(SNAP); } catch (e) {}
    Object.entries(o).forEach(([k, v]) => { if (mine(k) && typeof v === "string") ls.set(k, v); });
    setMeta({ code, h: hash(dump()), at: Date.now() });
    alert("기록을 되살렸어요. 앞으로 이 브라우저(프로필)에서 계속 쓰시면 돼요."); location.hash = ""; location.reload();
  }
  function ask() { const v = prompt("복구 코드 12자리를 넣어 주세요 (예: abcd-efgh-jkmn)"); if (v) restore(v); }

  function toast(html) {
    const t = document.createElement("div"); t.className = "bk-toast"; t.innerHTML = html + '<button type="button" aria-label="닫기">확인</button>';
    t.querySelector("button").onclick = () => t.remove(); document.body.appendChild(t);
  }
  /* 내 정보 탭에 넣는 칸 */
  function card() {
    const m = meta();
    const when = m.at ? new Date(m.at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : null;
    return `<section class="card"><div class="hd"><h2>기록 백업·복구</h2></div>
      <p class="sub">기록은 자동으로 서버에 백업돼요. 브라우저 정리 등으로 기록이 지워졌거나 다른 기기에서 이어 하려면 아래 복구 코드를 넣으세요. <b>캡처해 두세요.</b></p>
      ${m.code ? `<div class="bk-code">${fmt(m.code)}</div><p class="sub">${when ? "마지막 백업 " + when : "백업 준비 중"}</p>
        <button class="cta sub2" type="button" data-bk="copy">복구 코드 복사</button>` : `<p class="sub">팀을 고르면 백업이 시작돼요.</p>`}
      <button class="cta sub2" type="button" data-bk="restore">복구 코드로 기록 불러오기</button></section>`;
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-bk]"); if (!b) return;
    if (b.dataset.bk === "restore") ask();
    else if (b.dataset.bk === "copy") { const c = fmt(meta().code); (navigator.clipboard ? navigator.clipboard.writeText(c) : Promise.reject()).then(() => alert("복사했어요: " + c), () => prompt("복구 코드", c)); }
  });

  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") push(); });
  window.addEventListener("pagehide", () => push());
  setInterval(() => push(), 60e3);
  setTimeout(() => push(), 8e3);

  const css = document.createElement("style");
  css.textContent = `.bk-code{font:800 22px/1.2 ui-monospace,Menlo,monospace;letter-spacing:2px;text-align:center;padding:12px;margin:8px 0;border-radius:12px;background:var(--soft,#f6f5fd);color:var(--ink,#1d2033)}
  .bk-toast{position:fixed;left:12px;right:12px;bottom:84px;z-index:70;max-width:480px;margin:0 auto;padding:12px 14px;border-radius:14px;background:#1d2033;color:#fff;font-size:14px;line-height:1.5;box-shadow:0 10px 30px rgba(0,0,0,.25)}
  .bk-toast b{letter-spacing:1px}.bk-toast button{display:block;margin:8px 0 0 auto;border:0;border-radius:10px;padding:6px 14px;font-weight:700;background:#fff;color:#1d2033}`;
  document.head.appendChild(css);
  window.Backup = { push, restore, ask, card, code: () => fmt(meta().code) };
})();
