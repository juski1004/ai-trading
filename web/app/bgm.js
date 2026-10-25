/* 배경음악: 머리글 🔊 버튼으로 켜고 끔 (처음엔 꺼짐, 켜면 기억).
   - 메인: bgm/main.mp3 '저녁 정리' · AI 대결 화면(#vs): bgm/battle.mp3 '조용한 승부' (둘 다 드럼 없는 잔잔한 곡, bgm/calm.py)
   - 화면이 바뀌면 곡을 부드럽게 바꾸고, 본부장 브리핑(음성)이 열리면 잠깐 멈췄다가 닫으면 다시 재생.
   - 앱이 백그라운드로 가면 멈춤. 곡은 모두 직접 작곡·합성한 것 (bgm/*.py). */
(() => {
  const KEY = "aiLab.bgm.v1", VOL = 0.25, V = "?v=2"; // V: 곡을 바꾸면 올려서 옛 파일 캐시를 피함
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  let on = !!load().on, cur = null, src = "", held = false;
  const want = () => ((location.hash.slice(1) || "home").split("/")[0] === "vs" ? "bgm/battle.mp3" : "bgm/main.mp3") + V;

  function fade(a, to, ms, done) { // 같은 곡에 겹친 페이드는 마지막 것만 살림
    clearInterval(a._fade);
    const from = a.volume, t0 = Date.now();
    a._fade = setInterval(() => {
      const k = Math.min(1, (Date.now() - t0) / ms);
      a.volume = Math.max(0, Math.min(1, from + (to - from) * k));
      if (k >= 1) { clearInterval(a._fade); if (done) done(); }
    }, 40);
  }
  function play() {
    if (!on || held || document.hidden) return;
    const s = want();
    if (cur && src === s) { if (cur.paused) { cur.play().catch(() => {}); fade(cur, VOL, 600); } return; }
    const old = cur; if (old) fade(old, 0, 700, () => old.pause());
    cur = new Audio(s); cur.loop = true; cur.volume = 0; src = s;
    cur.play().then(() => fade(cur, VOL, 900)).catch(() => {});
  }
  function stop() { if (cur) { const a = cur; fade(a, 0, 400, () => a.pause()); } }

  const btn = document.getElementById("bgmBtn");
  function paint() {
    if (!btn) return;
    btn.textContent = on ? "🔊" : "🔈";
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.setAttribute("aria-label", on ? "배경음악 끄기" : "배경음악 켜기");
    btn.title = on ? "배경음악 끄기" : "배경음악 켜기";
  }
  if (btn) btn.addEventListener("click", () => { on = !on; save({ on }); paint(); on ? play() : stop(); });
  paint();

  addEventListener("hashchange", play);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : play()));
  // 브리핑 음성과 겹치지 않게
  document.addEventListener("click", e => { if (e.target.id === "openBrief") { held = true; stop(); } });
  addEventListener("message", e => { if (e.origin === location.origin && (e.data || {}).type === "briefClose") { held = false; play(); } });
  document.addEventListener("click", e => { if (held && e.target.classList && e.target.classList.contains("bover")) { held = false; setTimeout(play, 50); } });
  // 휴대폰 브라우저는 사용자가 한 번 눌러야 소리를 낼 수 있음 → 켜 둔 상태면 첫 터치 때 시작
  const kick = () => { play(); removeEventListener("pointerdown", kick); };
  if (on) addEventListener("pointerdown", kick);
  window.Bgm = { play, stop, isOn: () => on };
})();
