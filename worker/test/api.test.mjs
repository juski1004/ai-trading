// 랭킹(월간 시즌·리그)과 친구 초대 API 시험 — 메모리 KV로 실제 fetch 처리기를 그대로 부른다.
import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

function memKV() {
  const m = new Map();
  return {
    m,
    async get(k, t) { const v = m.get(k); return v == null ? null : t === "json" ? JSON.parse(v) : v; },
    async put(k, v) { m.set(k, String(v)); },
    async delete(k) { m.delete(k); },
    async list({ prefix = "" } = {}) { return { keys: [...m.keys()].filter(k => k.startsWith(prefix)).map(name => ({ name })), list_complete: true }; },
  };
}
const call = async (env, path, body) => {
  const req = new Request("https://w.example" + path, body ? { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json", Origin: "https://juski1004.github.io" } } : { headers: { Origin: "https://juski1004.github.io" } });
  const r = await worker.fetch(req, env); return { status: r.status, body: await r.json() };
};
const season = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 7);

test("시즌 랭킹: 리그별로 나뉘고 수익률 순", async () => {
  const env = { KV: memKV() };
  await call(env, "/rank", { id: "aaaaaaaa1", nick: "사장님", ret: 3.2, league: "rookie", days: 30 });
  await call(env, "/rank", { id: "bbbbbbbb2", nick: "대표님", ret: 7.5, league: "rookie", days: 30 });
  await call(env, "/rank", { id: "cccccccc3", nick: "고수", ret: 20, league: "pro", days: 30 });
  const r = await call(env, "/rank?id=aaaaaaaa1&league=rookie");
  assert.equal(r.body.season, season());
  assert.equal(r.body.total, 2);
  assert.deepEqual(r.body.top.map(x => x.nick), ["대표님", "사장님"]);
  assert.equal(r.body.me.rank, 2);
  const p = await call(env, "/rank?league=pro");
  assert.equal(p.body.total, 1);
});

test("리그를 옮기면 옛 리그에서 빠진다", async () => {
  const env = { KV: memKV() };
  await call(env, "/rank", { id: "aaaaaaaa1", nick: "a", ret: 1, league: "rookie" });
  await call(env, "/rank", { id: "aaaaaaaa1", nick: "a", ret: 2, league: "pro" });
  assert.equal((await call(env, "/rank?league=rookie")).body.total, 0);
  assert.equal((await call(env, "/rank?league=pro")).body.total, 1);
});

test("지난 시즌 내 순위를 돌려준다", async () => {
  const env = { KV: memKV() }, s = season();
  const [y, m] = s.split("-").map(Number), last = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
  for (const [id, ret] of [["xxxxxxxx1", 9], ["aaaaaaaa1", 5], ["yyyyyyyy1", 1]])
    await env.KV.put(`rank:${last}:rookie:${id}`, JSON.stringify({ id, nick: id, ret }));
  const r = await call(env, "/rank?id=aaaaaaaa1&league=rookie");
  assert.deepEqual(r.body.last, { season: last, league: "rookie", rank: 2, total: 3, ret: 5 });
});

test("잘못된 기록은 거절", async () => {
  const env = { KV: memKV() };
  assert.equal((await call(env, "/rank", { id: "x", ret: 1 })).status, 400);
  assert.equal((await call(env, "/rank", { id: "aaaaaaaa1", ret: "1" })).status, 400);
});

test("친구 초대: 기기 하나는 한 번만, 자기 코드는 못 씀, 30명까지", async () => {
  const env = { KV: memKV() };
  assert.equal((await call(env, "/invite", { code: "abc123", id: "newuser01" })).status, 200);
  assert.equal((await call(env, "/invite", { code: "abc123", id: "newuser01" })).status, 409);
  assert.equal((await call(env, "/invite", { code: "abc123", id: "abc123zzzz" })).status, 400); // 자기 코드
  assert.equal((await call(env, "/invite?code=abc123")).body.count, 1);
  for (let i = 2; i <= 30; i++) await call(env, "/invite", { code: "abc123", id: "newuser" + String(i).padStart(2, "0") });
  assert.equal((await call(env, "/invite?code=abc123")).body.count, 30);
  assert.equal((await call(env, "/invite", { code: "abc123", id: "newuser99" })).status, 409);
});
