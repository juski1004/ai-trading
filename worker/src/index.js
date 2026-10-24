/* AI 투자연구소 알림·랭킹 서버 (Cloudflare Workers 무료 플랜).
   - 웹 푸시: 앱이 닫혀 있어도 평일 18:00 '본부장 브리핑', 18:10 '오늘의 추천' 알림 (데이터가 오늘 것일 때만, 하루 한 번)
   - 랭킹: 모의투자 참여자(동의한 사람만)의 같은 기간 수익률 순위
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

/* ---------- 랭킹 ---------- */
const clean = s => String(s || "").replace(/[<>"'`]/g, "").trim().slice(0, 12) || "익명";
async function rankList(env) {
  const out = [], since = Date.now() - 21 * 864e5; let cursor;
  do {
    const page = await env.KV.list({ prefix: "rank:", cursor }); cursor = page.list_complete ? null : page.cursor;
    for (const k of page.keys) { const r = await env.KV.get(k.name, "json"); if (r && r.at >= since) out.push(r); }
  } while (cursor);
  return out.sort((a, b) => b.ret - a.ret);
}

/* ---------- 정해진 시각 알림 ---------- */
async function scheduled(cron, env) {
  const today = todayKST(), get = f => fetch(`${SITE}/data/${f}?t=${Date.now()}`, { cf: { cacheTtl: 0 } }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const meta = await get("meta.json");
  if (!meta || !meta.updated || kstDate(meta.updated) !== today) return { skip: "오늘 데이터 아직 없음" };
  const out = {};
  if (!(await env.KV.get(`sent:brief:${today}`))) {
    out.brief = await broadcast(env, { title: "본부장이 브리핑을 가져왔습니다", body: "오늘 장 마감 브리핑이 준비됐어요. 눌러서 확인하세요.", url: "./#home", tag: "brief" });
    await env.KV.put(`sent:brief:${today}`, "1", { expirationTtl: 3 * 86400 });
  }
  if (cron !== "0 9 * * 1-5" && !(await env.KV.get(`sent:pick:${today}`))) {
    const pick = await get("pick.json");
    if (pick && pick.date === today) {
      out.pick = await broadcast(env, pick.found
        ? { title: `오늘의 추천 · ${pick.name}`, body: (pick.reason || "추천 보고서가 올라왔어요.").slice(0, 110), url: "./#pick", tag: "pick" }
        : { title: "오늘은 추천을 쉬어 갑니다", body: "조건을 모두 통과한 종목이 없어요. 내일 다시 찾아볼게요.", url: "./#home", tag: "pick" });
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
        const st = await sendPush(rec.sub, { title: "알림이 켜졌어요", body: "평일 18:00 브리핑, 18:10 추천 종목을 알려 드릴게요.", url: "./#home", tag: "test" }, await vapid(env));
        return json(req, { ok: st < 300, status: st });
      }
      if (p === "/rank" && req.method === "POST") {
        const b = await req.json();
        if (!/^[a-z0-9]{8,32}$/.test(b.id || "") || typeof b.ret !== "number" || !isFinite(b.ret)) return json(req, { error: "bad record" }, 400);
        const rec = { id: b.id, nick: clean(b.nick), ret: Math.max(-100, Math.min(1000, Math.round(b.ret * 100) / 100)),
          ai: typeof b.ai === "number" && isFinite(b.ai) ? Math.round(b.ai * 100) / 100 : null,
          start: String(b.start || "").slice(0, 10), days: Math.max(1, Math.min(120, b.days | 0)), done: !!b.done, at: Date.now() };
        await env.KV.put("rank:" + rec.id, JSON.stringify(rec), { expirationTtl: 60 * 86400 });
        return json(req, { ok: true });
      }
      if (p === "/rank") {
        const list = await rankList(env), id = url.searchParams.get("id"), i = id ? list.findIndex(r => r.id === id) : -1;
        const pub = r => ({ nick: r.nick, ret: r.ret, ai: r.ai, days: r.days, done: r.done, start: r.start, me: r.id === id });
        return json(req, { total: list.length, top: list.slice(0, 20).map(pub), me: i >= 0 ? { rank: i + 1, ...pub(list[i]) } : null });
      }
      if (p === "/run" && url.searchParams.get("cron")) { // 수동 점검용: 오늘 이미 보냈으면 다시 안 보냄
        return json(req, await scheduled(url.searchParams.get("cron"), env));
      }
      return json(req, { error: "not found" }, 404);
    } catch (e) {
      return json(req, { error: String(e && e.message || e) }, 500);
    }
  },
  async scheduled(event, env, ctx) { ctx.waitUntil(scheduled(event.cron, env)); },
};
