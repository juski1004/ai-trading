/* 튜토리얼: 화면마다 그 부분을 밝게 비추며 설명하고, 마지막엔 직접 눌러 모의투자 주문까지 넣어 본다.
   - 단계: 홈(출석·브리핑·리포트) → 분석(검색·필터·목록) → 종목 화면(점수 읽는 법·목표가/손절가·차트·직원 의견) → 모의투자(시작·사기/팔기·수량·주문) → 내 계좌·알파 비교
   - 예시 종목은 시가총액 1위 삼성전자 (추천이 아니라 예시). 사고팔라고 권하지 않는다.
   - '직접 눌러 보세요' 단계는 그 버튼을 누르면 다음으로 넘어감. 대상이 화면에 없으면(이미 게임 중 등) 그 단계는 건너뜀.
   - 처음 팀을 고른 뒤 한 번 권하고, '사용법' 창에서 다시 볼 수 있다. 끝까지 하면 연구소 포인트 +100P (한 번만).
   - 튜토리얼에서 넣은 게임 시작·주문은 연습이라, 끝내거나 그만두면 시작 전 상태로 되돌린다
     (시작할 때 게임 기록을 aiLab.tour.snap.v1 에 떠 두었다가 복원. 중간에 앱을 닫아도 다음에 열면 복원)
   - 저장: aiLab.tour.v1 {done, offered} */
(() => {
  const KEY = "aiLab.tour.v1", EX = "005930.KS";
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  /* 연습 주문 되돌리기용: 튜토리얼 시작 전 게임 기록 */
  const SNAP = "aiLab.tour.snap.v1", GKEYS = ["aiLab.game.v1", "aiLab.games.v1"];
  function snap() {
    try { const o = {}; GKEYS.forEach(k => { o[k] = localStorage.getItem(k); }); localStorage.setItem(SNAP, JSON.stringify(o)); } catch (e) {}
  }
  function restore() {
    try {
      const raw = localStorage.getItem(SNAP); if (!raw) return;
      const o = JSON.parse(raw);
      GKEYS.forEach(k => { if (o[k] == null) localStorage.removeItem(k); else localStorage.setItem(k, o[k]); });
      localStorage.removeItem(SNAP);
    } catch (e) {}
    if (window.Game && Game.reload) Game.reload();
  }
  const go = h => { if (location.hash !== "#" + h) location.hash = h; };

  // [화면, 비출 곳, 제목, 설명, 방식('next'|'click'), 들어가기 전 할 일]
  const STEPS = [
    ["home", null, "1분 튜토리얼을 시작할게요", "화면마다 무엇을 보는지 짚어 보고, 마지막엔 <b>가상 돈으로 직접 주문</b>까지 넣어 봐요. 진짜 돈은 쓰지 않아요.", "next"],
    ["home", ".pt-strip", "출석과 연구소 포인트", "매일 열면 출석 포인트가 쌓여요. 연속 출석일수록 더 많이 받아요. 포인트로 깊은 정보를 열거나 게임 투자금을 늘릴 수 있어요.", "next"],
    ["home", ".bcard", "저녁 6시 본부장 브리핑", "평일 장 마감 뒤 담당 본부장이 오늘 시장을 8장으로 짚어 줘요. 퇴근길에 이것부터 보세요.", "next"],
    ["home", ".dk-tabs", "오늘의 리포트", "마감 현황·경제지표·뉴스·공시·수급·실적 발표·알파의 선택을 옆으로 넘겨 봐요. 위 탭을 눌러도 돼요.", "next"],
    ["home", 'nav a[data-tab="analysis"]', "종목을 찾아볼게요", "아래 <b>종목검색</b> 탭을 눌러 보세요.", "click"],
    ["analysis", ".search", "검색", "종목 이름이나 코드(예: 005930)로 찾아요. AI가 매일 분석하는 대형주 78종목과, 시세로 거래할 수 있는 상위 종목이 나와요.", "next"],
    ["analysis", '.chips[aria-label="분류"]', "필터", "AI 판단이 <b>긍정·중립·부정</b>인 종목만 골라 볼 수 있어요. ★ 관심은 내가 별표한 종목이에요.", "next"],
    ["analysis", "#view .list", "AI 점수 순 목록", "점수가 높은 순서예요. 오른쪽에 종가·등락률·AI 점수가 있어요. 예시로 <b>삼성전자</b> 화면을 열어 볼게요 (추천이 아니라 예시예요).", "next", () => go("analysis/" + encodeURIComponent(EX))],
    ["analysis/" + EX, ".ring", "AI 종합 점수 읽는 법", "100점 만점에 <b>50점이 중간</b>이에요. 차트·거래량·시장 흐름·진입 자리를 합친 점수예요. 65점 이상이면 '긍정', 35점 이하면 '부정'으로 표시돼요. 점수는 참고 자료예요.", "next"],
    ["analysis/" + EX, ".tiles", "목표가·손절가와 세부 점수", "<b>참고 목표가</b>는 현재가 +10%, <b>참고 손절가</b>는 −5%예요. 게임의 자동 익절·손절 기준과 같아요. 재무 점수(실적)·기술 점수(차트)는 5점 만점, 리스크는 하루 평균 변동폭이에요.", "next"],
    ["analysis/" + EX, "#acCard", "차트 보는 법", "<b>일봉·주봉·월봉</b>을 바꿔 보고, 두 손가락으로 확대·축소, 밀어서 지난 기간을 봐요. 빨간 봉은 오른 날, 파란 봉은 내린 날. 선은 5·20·60일 이동평균, 점선은 참고 목표가·손절가예요. <b>⛶</b>를 누르면 가로 전체 화면이에요.", "next"],
    ["analysis/" + EX, ".ops", "AI 직원 6명의 의견", "직원마다 맡은 분야(시장·수급·차트·진입·리스크)로 의견을 내요. 막대가 <b>오른쪽(빨강)이면 긍정</b>, 왼쪽(파랑)이면 부정이에요. 의견이 엇갈리면 더 신중하게 보세요.", "next"],
    ["analysis/" + EX, 'a.cta[href^="#game/"]', "모의투자로 연습해 볼까요?", "아래 빨간 <b>사기</b> 버튼을 눌러 보세요. 가상 돈이라 부담 없어요.", "click"],
    ["game/" + EX, '[data-g="start"]', "게임 시작", "기간을 고르고 <b>1,000만 원으로 시작하기</b>를 눌러 보세요. 포인트를 모으면 5,000만·1억 원으로도 시작할 수 있어요. 같은 기간 AI 팀 '알파'·코스피와 수익률을 겨뤄요.", "click"],
    ["game/" + EX, ".g-side2", "사기 · 팔기", "사기/팔기를 고르는 곳이에요. 지금은 <b>사기</b>예요.", "next"],
    ["game/" + EX, '[data-g="frac"][data-v="0.1"]', "수량 정하기", "직접 숫자를 넣거나 10%·25%·50%·최대 버튼을 써요. <b>10%</b>를 눌러 보세요. 한 종목에 몰빵하지 않는 게 스윙의 기본이에요.", "click"],
    ["game/" + EX, '[data-g="order"]', "주문 넣기", "이제 주문 버튼을 눌러 보세요. 장 마감 뒤 데이터가 들어온 날엔 <b>그날 종가로 바로 체결</b>, 그 전엔 <b>다음 장 마감 종가로 예약</b>돼요. 튜토리얼 주문은 <b>연습이라 끝나면 지워져요</b>.", "click"],
    ["game/" + EX, ".g-msg", "주문 완료!", "이렇게 하루 한 번, 종가로 사고파는 게 이 앱의 스윙 매매예요. 장중에 시세를 볼 필요가 없어요. (방금 주문은 튜토리얼이 끝나면 자동으로 지워져요)", "next", () => go("game")],
    ["game", ".g-auto", "자동 손절·익절", "켜 두면 −5%·+10%에 닿은 날 종가로 알아서 정리돼요. 원칙을 지키는 연습이에요.", "next"],
    ["game", ".g-line", "알파와 비교", "같은 기간 AI 팀 알파·코스피보다 잘하고 있는지 보여 줘요. 누르면 AI 대결 화면으로 가요. 게임을 완주하고 알파를 이기면 포인트를 더 받아요.", "next"],
    ["game", null, "튜토리얼 끝!", "수고하셨어요. 연구소 포인트 <b>+100P</b>를 드렸어요. 연습으로 넣은 게임·주문은 지웠으니, 이제 <b>거래하기</b> 탭에서 진짜로 시작해 보세요. 위쪽 <b>사용법</b> 버튼에서 언제든 다시 볼 수 있어요.", "next"],
  ];

  let i = -1, waitT = null, clickOff = null;
  const $ = s => s && document.querySelector(s);

  function ui() {
    let box = document.getElementById("tourBox");
    if (!box) {
      document.body.insertAdjacentHTML("beforeend", `<div id="tourSpot" class="tour-spot" hidden></div><div id="tourDim" class="tour-dim" hidden></div>
        <div id="tourBox" class="tour-box" role="dialog" aria-live="polite"><div class="tour-step"></div><h3></h3><p></p>
        <div class="tour-act"><button type="button" data-tour="skip" class="tour-skip">그만하기</button><span></span><button type="button" data-tour="prev">이전</button><button type="button" data-tour="next" class="tour-next">다음</button></div></div>`);
      box = document.getElementById("tourBox");
    }
    return box;
  }
  function place(el) {
    const spot = document.getElementById("tourSpot"), dim = document.getElementById("tourDim"), box = ui();
    if (!el) { spot.hidden = true; dim.hidden = false; box.style.top = "50%"; box.style.transform = "translate(-50%,-50%)"; return; }
    dim.hidden = true; spot.hidden = false;
    const r = el.getBoundingClientRect(), pad = 6;
    Object.assign(spot.style, { top: r.top - pad + "px", left: r.left - pad + "px", width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px" });
    const bh = box.offsetHeight || 180, below = r.bottom + 14 + bh < innerHeight - 90;
    box.style.transform = "translateX(-50%)";
    box.style.top = (below ? r.bottom + 14 : Math.max(12, r.top - bh - 14)) + "px";
  }
  function show() {
    clearTimeout(waitT); if (clickOff) { clickOff(); clickOff = null; }
    const st = STEPS[i]; if (!st) return end(true);
    const [route, sel, title, body, mode] = st;
    if ((location.hash.slice(1) || "home") !== route) go(route);
    const t0 = Date.now();
    (function wait() {
      const el = $(sel);
      if (sel && !el) {
        if (Date.now() - t0 > 3000) { i++; return show(); }   // 화면에 없으면 이 단계는 건너뜀 (이미 게임 중 등)
        waitT = setTimeout(wait, 150); return;
      }
      if (el) el.scrollIntoView({ block: "center", behavior: "instant" in document.documentElement.style ? "instant" : "auto" });
      setTimeout(() => {
        const box = ui();
        box.querySelector(".tour-step").textContent = `${i + 1} / ${STEPS.length}`;
        box.querySelector("h3").textContent = title;
        box.querySelector("p").innerHTML = body + (mode === "click" ? '<span class="tour-tap">👆 직접 눌러 보세요</span>' : "");
        box.querySelector('[data-tour="next"]').hidden = mode === "click";
        box.querySelector('[data-tour="next"]').textContent = i === STEPS.length - 1 ? "끝내기" : "다음";
        box.querySelector('[data-tour="prev"]').hidden = i === 0;
        document.body.classList.add("tour-on");
        place(el);
        if (mode === "click" && el && el.disabled) box.querySelector('[data-tour="next"]').hidden = false; // 눌러 볼 수 없는 상태면 '다음'으로
        if (mode === "click" && el && !el.disabled) {
          // 게임 화면은 document 단계에서 클릭을 처리하고 멈추므로, 그보다 먼저인 window 단계에서 '그 버튼을 눌렀는지'만 본다
          const h = e => { if (!e.target.closest || !e.target.closest(sel)) return; off(); setTimeout(() => { i++; show(); }, 700); };
          const off = () => window.removeEventListener("click", h, true);
          window.addEventListener("click", h, true); clickOff = off;
        }
      }, 120);
    })();
  }
  function next() { const st = STEPS[i]; if (st && st[5]) st[5](); i++; show(); }
  function end(finished) {
    clearTimeout(waitT); if (clickOff) { clickOff(); clickOff = null; }
    ["tourBox", "tourSpot", "tourDim"].forEach(id => document.getElementById(id)?.remove());
    document.body.classList.remove("tour-on");
    const T = load(); T.offered = true;
    if (finished && !T.done) { T.done = true; if (window.Daily && Daily.earn) Daily.earn(100, "튜토리얼 완료"); window.dispatchEvent(new CustomEvent("aiLab:tourDone")); }
    save(T); i = -1;
    restore(); // 연습으로 넣은 게임 시작·주문 되돌리기
  }
  function start() { snap(); i = 0; show(); }
  restore(); // 튜토리얼 중간에 앱을 닫았다면 다음에 열 때 되돌림

  document.addEventListener("click", e => {
    const b = e.target.closest("[data-tour]"); if (!b) return;
    const a = b.dataset.tour;
    if (a === "next") { if (i >= STEPS.length - 1) end(true); else next(); }
    else if (a === "prev" && i > 0) { i--; show(); }
    else if (a === "skip") end(false);
    else if (a === "start") { document.getElementById("tourAsk")?.remove(); start(); }
    else if (a === "later") { document.getElementById("tourAsk")?.remove(); const T = load(); T.offered = true; save(T); }
  });
  addEventListener("resize", () => { if (i >= 0) place($(STEPS[i][1])); });
  addEventListener("scroll", () => { if (i >= 0) place($(STEPS[i][1])); }, { passive: true });

  /* 처음 팀을 고른 뒤 한 번 권하기 */
  function offer() {
    const T = load(); if (T.offered || T.done || document.getElementById("tourAsk")) return;
    const sns = window.Metrics && Metrics.social(); // 인스타(카드·릴스·DM 링크)로 들어온 사람에겐 선공개 환영 인사
    document.body.insertAdjacentHTML("beforeend", `<div id="tourAsk" class="tour-ask" role="dialog" aria-modal="true"><div class="tour-box2">
      ${sns ? `<div class="tour-step">팔로워 선공개</div><h3>인스타에서 오셨군요, 반가워요!</h3>
      <p>장마감 카드뉴스를 만드는 AI 직원들이 일하는 곳이에요. 먼저 <b>1분 튜토리얼</b>로 둘러봐요.</p><p style="margin-top:6px">` : `<div class="tour-step">처음이시죠?</div><h3>1분 튜토리얼 해 볼까요?</h3>
      <p>`}
      화면 보는 법부터 종목 분석, <b>가상 돈으로 직접 주문</b>까지 같이 해 봐요. 끝까지 하면 <b>+100P</b>.</p>
      <button type="button" class="cta" data-tour="start">시작하기</button><button type="button" class="cta sub2" data-tour="later">나중에 (사용법 버튼에서)</button></div></div>`);
  }

  const css = document.createElement("style");
  css.textContent = `
  .tour-spot{position:fixed;z-index:80;border-radius:16px;box-shadow:0 0 0 9999px rgba(29,32,51,.55),0 0 0 3px #b9b2ff;pointer-events:none;transition:all .25s ease}
  .tour-dim{position:fixed;inset:0;z-index:80;background:rgba(29,32,51,.55)}
  .tour-box{position:fixed;z-index:81;left:50%;width:min(420px,calc(100% - 24px));background:#fff;border-radius:22px;padding:16px 16px 12px;box-shadow:0 18px 50px rgba(20,20,60,.35);animation:rise .25s ease both}
  .tour-box h3,.tour-box2 h3{margin:4px 0 6px;font-size:18px;letter-spacing:-.4px}.tour-box p,.tour-box2 p{margin:0;font-size:14.5px;line-height:1.6;color:var(--fg,#1d2033)}
  .tour-step{display:inline-block;font-size:12px;font-weight:700;color:var(--lav-d,#6c5ce7);background:var(--lav-s,#efedff);border-radius:10px;padding:2px 9px}
  .tour-tap{display:block;margin-top:8px;font-weight:800;color:var(--lav-d,#6c5ce7)}
  .tour-act{display:flex;align-items:center;gap:8px;margin-top:12px}.tour-act span{flex:1}
  .tour-act button{border:0;border-radius:12px;padding:9px 14px;font:inherit;font-weight:700;font-size:13.5px;background:var(--lav-s,#efedff);color:var(--lav-d,#6c5ce7)}
  .tour-act .tour-next{background:var(--lav-d,#6c5ce7);color:#fff}.tour-act .tour-skip{background:none;color:var(--muted,#6b7088);padding-left:2px}
  .tour-ask{position:fixed;inset:0;z-index:82;background:rgba(29,32,51,.4);display:flex;align-items:flex-end;justify-content:center;padding:16px}
  .tour-box2{width:min(480px,100%);background:#fff;border-radius:26px;padding:20px 18px 16px;box-shadow:0 24px 60px rgba(40,50,90,.3);animation:rise .3s ease both}.tour-box2 .cta{margin-top:12px}`;
  document.head.appendChild(css);

  window.Tour = { start, offer, done: () => !!load().done };
})();
