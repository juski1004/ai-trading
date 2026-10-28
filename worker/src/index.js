/* AI 투자연구소 알림·랭킹 서버 (Cloudflare Workers 무료 플랜).
   - 웹 푸시: 앱이 닫혀 있어도 평일 18:00 '본부장 브리핑', 18:10 '알파의 선택' 알림 (데이터가 오늘 것일 때만, 하루 한 번)
   - 랭킹: 월간 시즌 리그 (동의한 사람만). 리그 2개: 새내기(완주한 게임 3판 미만) · 일반. 지난 시즌 순위도 돌려줘서 앱이 배지·보상을 준다
   - 친구 초대: 초대 코드별 가입 수 (새 기기 하나는 한 번만)
   - 사용 집계: 날짜별 숫자만 (오늘 연 기기 수, 새 기기, 홈 화면 설치, 튜토리얼 완료, 첫 주문, 3·7일째 재방문, 들어온 경로). 개인 정보·기기 id 저장 없음
   저장소는 KV 하나(바인딩 이름 KV). VAPID 열쇠는 처음 쓸 때 만들어 KV에 둔다. 외부 비밀값 없음. */
import { makeVapid, sendPush } from "./push.js";

const SITE = "https://juski1004.github.io/ai-trading";
const ORIGINS = ["https://juski1004.github.io", "http://localhost:8765"];
const todayKST = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const kstDate = iso => new Date(new Date(iso).getTime() + 9 * 3600e3).toISOString().slice(0, 10);

async function sha(s) {
  const h = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  return [...h.slice(0, 12)].map(b => b.toString(16).padStart(2, "0")).join("");
}
async function vapid(env) {
  let v = await env.KV.get("vapid", "json");
  if (!v) { v = await makeVapid(); await env.KV.put("vapid", JSON.stringify(v)); }
  return v;
}

function cors(req) {
  const o = req.headers.get("Origin") || "";
  return { "Access-Control-Allow-Origin": ORIGINS.includes(o) ? o : ORIGINS[0], "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", Vary: "Origin" };
}
const json = (req, data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...cors(req) } });

/* ---------- 구독 ---------- */
const validSub = s => s && typeof s.endpoint === "string" && /^https:\/\//.test(s.endpoint) && s.endpoint.length < 1000 && s.keys && typeof s.keys.p256dh === "string" && typeof s.keys.auth === "string";

async function broadcast(env, payload) {
  const v = await vapid(env); let sent = 0, gone = 0, cursor;
  do {
    const page = await env.KV.list({ prefix: "sub:", cursor }); cursor = page.list_complete ? null : page.cursor;
    for (const k of page.keys) {
      const rec = await env.KV.get(k.name, "json"); if (!rec) continue;
      try {
        const st = await sendPush(rec.sub, payload, v);
        if (st === 404 || st === 410) { await env.KV.delete(k.name); gone++; } else if (st < 300) sent++;
      } catch (e) { /* 한 사람 실패는 건너뜀 */ }
    }
  } while (cursor);
  return { sent, gone };
}

/* ---------- 랭킹 (월간 시즌) ---------- */
const clean = s => String(s || "").replace(/[<>"'`]/g, "").trim().slice(0, 12) || "익명";
const seasonOf = (d = todayKST()) => d.slice(0, 7);                  // "2026-10"
const prevSeason = s => { const [y, m] = s.split("-").map(Number); return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`; };
const LEAGUES = ["rookie", "pro"];
async function rankList(env, season, league) {
  const cacheKey = `board:${season}:${league}`, hit = await env.KV.get(cacheKey, "json");
  if (hit && hit.at > Date.now() - 60e3) return hit.list;                 // 1분 캐시 (KV 읽기 아끼기)
  const out = []; let cursor;
  do {
    const page = await env.KV.list({ prefix: `rank:${season}:${league}:`, cursor }); cursor = page.list_complete ? null : page.cursor;
    for (const k of page.keys) { const r = await env.KV.get(k.name, "json"); if (r) out.push(r); }
  } while (cursor);
  out.sort((a, b) => b.ret - a.ret);
  await env.KV.put(cacheKey, JSON.stringify({ at: Date.now(), list: out }), { expirationTtl: 120 * 86400 });
  return out;
}

/* ---------- 사용 집계 (하루 한 키: st:날짜 → {이벤트: 수}) ---------- */
const EVENTS = ["open", "new", "install", "tour", "trade", "d3", "d7", "push"];
const SOURCES = ["insta", "reel", "dm", "card", "invite", "archive", "direct"];
async function stats(env, days) {
  const out = [], t = Date.now() + 9 * 3600e3;
  for (let i = 0; i < days; i++) {
    const d = new Date(t - i * 86400e3).toISOString().slice(0, 10);
    out.push({ date: d, ...((await env.KV.get("st:" + d, "json")) || {}) });
  }
  return out;
}

/* ---------- 정해진 시각 알림 ---------- */
async function scheduled(cron, env) {
  const today = todayKST(), get = f => fetch(`${SITE}/data/${f}?t=${Date.now()}`, { cf: { cacheTtl: 0 } }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const meta = await get("meta.json");
  if (!meta || !meta.updated || kstDate(meta.updated) !== today) return { skip: "오늘 데이터 아직 없음" };
  const out = {};
  if (!(await env.KV.get(`sent:brief:${today}`))) {
    out.brief = await broadcast(env, { title: "본부장이 브리핑을 가져왔습니다", body: "오늘 장 마감 브리핑이 준비됐어요. 모의투자 예약·지정가 주문 체결 결과도 앱을 열면 바로 알려 드려요.", url: "./#home", tag: "brief" });
    await env.KV.put(`sent:brief:${today}`, "1", { expirationTtl: 3 * 86400 });
  }
  if (cron !== "0 9 * * 1-5" && !(await env.KV.get(`sent:pick:${today}`))) {
    const pick = await get("pick.json");
    if (pick && pick.date === today) {
      out.pick = await broadcast(env, pick.found
        ? { title: `알파의 선택 · ${pick.name}`, body: "알파 팀이 오늘 게임 계좌에 담은 종목이 공개됐어요. (게임·참고용)", url: "./#pick", tag: "pick" }
        : { title: "오늘 알파는 쉬어 갑니다", body: "조건을 모두 통과한 종목이 없어 알파 팀이 오늘은 사지 않았어요.", url: "./#home", tag: "pick" });
      await env.KV.put(`sent:pick:${today}`, "1", { expirationTtl: 3 * 86400 });
    }
  }
  return out;
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });
    const url = new URL(req.url), p = url.pathname;
    try {
      if (p === "/" || p === "/health") return json(req, { ok: true, name: "ai-lab" });
      if (p === "/vapid") return json(req, { key: (await vapid(env)).pub });
      if (req.method === "POST" && p === "/subscribe") {
        const { sub } = await req.json(); if (!validSub(sub)) return json(req, { error: "bad subscription" }, 400);
        await env.KV.put("sub:" + (await sha(sub.endpoint)), JSON.stringify({ sub, at: Date.now() }));
        return json(req, { ok: true });
      }
      if (req.method === "POST" && p === "/unsubscribe") {
        const { endpoint } = await req.json(); if (endpoint) await env.KV.delete("sub:" + (await sha(endpoint)));
        return json(req, { ok: true });
      }
      if (req.method === "POST" && p === "/test") { // 구독한 그 기기에만 확인용 알림
        const { endpoint } = await req.json(); const rec = endpoint && (await env.KV.get("sub:" + (await sha(endpoint)), "json"));
        if (!rec) return json(req, { error: "not subscribed" }, 404);
        const st = await sendPush(rec.sub, { title: "알림이 켜졌어요", body: "평일 18:00 브리핑, 18:10 알파의 선택을 알려 드릴게요.", url: "./#home", tag: "test" }, await vapid(env));
        return json(req, { ok: st < 300, status: st });
      }
      if (p === "/rank" && req.method === "POST") {
        const b = await req.json();
        if (!/^[a-z0-9]{8,32}$/.test(b.id || "") || typeof b.ret !== "number" || !isFinite(b.ret)) return json(req, { error: "bad record" }, 400);
        const season = seasonOf(), league = LEAGUES.includes(b.league) ? b.league : "rookie";
        const rec = { id: b.id, nick: clean(b.nick), ret: Math.max(-100, Math.min(1000, Math.round(b.ret * 100) / 100)),
          ai: typeof b.ai === "number" && isFinite(b.ai) ? Math.round(b.ai * 100) / 100 : null, league,
          start: String(b.start || "").slice(0, 10), days: Math.max(1, Math.min(120, b.days | 0)), done: !!b.done, at: Date.now() };
        for (const l of LEAGUES) if (l !== league) await env.KV.delete(`rank:${season}:${l}:${rec.id}`); // 리그가 바뀌면 옛 리그에서 빼기
        await env.KV.put(`rank:${season}:${league}:${rec.id}`, JSON.stringify(rec), { expirationTtl: 120 * 86400 });
        await env.KV.delete(`board:${season}:${league}`);
        return json(req, { ok: true, season, league });
      }
      if (p === "/rank") {
        const id = url.searchParams.get("id"), league = LEAGUES.includes(url.searchParams.get("league")) ? url.searchParams.get("league") : "rookie";
        const season = seasonOf(), last = prevSeason(season);
        const list = await rankList(env, season, league), i = id ? list.findIndex(r => r.id === id) : -1;
        const pub = r => ({ nick: r.nick, ret: r.ret, ai: r.ai, days: r.days, done: r.done, start: r.start, me: r.id === id });
        let lastMe = null; // 지난 시즌 내 성적 (배지·보상용)
        if (id) for (const l of LEAGUES) {
          const L = await rankList(env, last, l), j = L.findIndex(r => r.id === id);
          if (j >= 0) { lastMe = { season: last, league: l, rank: j + 1, total: L.length, ret: L[j].ret }; break; }
        }
        return json(req, { season, league, total: list.length, top: list.slice(0, 20).map(pub), me: i >= 0 ? { rank: i + 1, ...pub(list[i]) } : null, last: lastMe });
      }
      /* ---------- 친구 초대 ---------- */
      if (p === "/invite" && req.method === "POST") {
        const b = await req.json();
        if (!/^[a-z0-9]{6,10}$/.test(b.code || "") || !/^[a-z0-9]{8,32}$/.test(b.id || "") || b.id.startsWith(b.code)) return json(req, { error: "bad code" }, 400);
        if (await env.KV.get("inv:" + b.id)) return json(req, { error: "already" }, 409);   // 이 기기는 이미 초대 코드를 썼음
        const n = +((await env.KV.get("invc:" + b.code)) || 0);
        if (n >= 30) return json(req, { error: "full" }, 409);                                 // 코드 하나로 최대 30명
        await env.KV.put("inv:" + b.id, b.code, { expirationTtl: 365 * 86400 });
        await env.KV.put("invc:" + b.code, String(n + 1), { expirationTtl: 365 * 86400 });
        return json(req, { ok: true });
      }
      if (p === "/invite") {
        const code = url.searchParams.get("code") || "";
        if (!/^[a-z0-9]{6,10}$/.test(code)) return json(req, { error: "bad code" }, 400);
        return json(req, { count: +((await env.KV.get("invc:" + code)) || 0) });
      }
      /* ---------- 기록 백업 (복구 코드 12자리) ----------
         브라우저가 저장 공간을 지워도 코드로 되살린다. 코드는 해시로만 저장(목록으로 못 봄). 400일 보관. */
      if (p === "/backup" && req.method === "POST") {
        const b = await req.json().catch(() => ({}));
        const code = String(b.code || "").toLowerCase().replace(/[^a-z0-9]/g, "");
        if (!/^[a-z0-9]{12}$/.test(code) || typeof b.data !== "string" || b.data.length > 300000) return json(req, { error: "bad backup" }, 400);
        try { JSON.parse(b.data); } catch (e) { return json(req, { error: "bad backup" }, 400); }
        await env.KV.put("bk:" + (await sha(code)), JSON.stringify({ at: Date.now(), data: b.data }), { expirationTtl: 400 * 86400 });
        return json(req, { ok: true });
      }
      if (p === "/backup") {
        const code = String(url.searchParams.get("code") || "").toLowerCase().replace(/[^a-z0-9]/g, "");
        if (!/^[a-z0-9]{12}$/.test(code)) return json(req, { error: "bad code" }, 400);
        const rec = await env.KV.get("bk:" + (await sha(code)), "json");
        return rec ? json(req, rec) : json(req, { error: "not found" }, 404);
      }
      /* ---------- 사용 집계 ---------- */
      if (p === "/hit" && req.method === "POST") {
        const b = await req.json().catch(() => ({}));
        const evs = (Array.isArray(b.ev) ? b.ev : [b.ev]).filter(e => EVENTS.includes(e)).slice(0, 8);
        if (!evs.length) return json(req, { error: "bad event" }, 400);
        const src = SOURCES.includes(b.src) ? b.src : "direct";
        const k = "st:" + todayKST(), cur = (await env.KV.get(k, "json")) || {};
        for (const ev of new Set(evs)) {
          cur[ev] = (cur[ev] || 0) + 1;
          if (ev === "new" || ev === "open") cur[`${ev}.${src}`] = (cur[`${ev}.${src}`] || 0) + 1;
        }
        await env.KV.put(k, JSON.stringify(cur), { expirationTtl: 400 * 86400 }); // 한 번에 묶어 써서 KV 쓰기 1회
        return json(req, { ok: true });
      }
      if (p === "/stats") {
        const days = Math.max(1, Math.min(60, +url.searchParams.get("days") || 14));
        return json(req, { days: await stats(env, days) });
      }
      // 수동 점검용 (오늘 이미 보냈으면 다시 안 보냄). 아무나 불러 알림을 앞당겨 보내지 못하게 비밀 키(RUN_KEY)가 맞을 때만
      if (p === "/run" && url.searchParams.get("cron") && env.RUN_KEY && url.searchParams.get("key") === env.RUN_KEY) {
        return json(req, await scheduled(url.searchParams.get("cron"), env));
      }
      return json(req, { error: "not found" }, 404);
    } catch (e) {
      console.error(e); // 내부 오류 내용은 밖으로 보이지 않게
      return json(req, { error: "server error" }, 500);
    }
  },
  async scheduled(event, env, ctx) { ctx.waitUntil(scheduled(event.cron, env)); },
};
