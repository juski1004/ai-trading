import test from "node:test";
import assert from "node:assert/strict";
import { plan, kstParts } from "../src/dispatch.js";

const kst = (iso) => Date.parse(iso + "+09:00");   // 한국시간 문자열 → ms
test("평일 장마감: 16:10·16:50 데이터, 17:50·19:20 릴스 게시", () => {
  assert.deepEqual(plan(kst("2026-11-03T16:10:00")), [{ kind: "data" }]);
  assert.deepEqual(plan(kst("2026-11-03T16:50:00")), [{ kind: "data" }]);
  assert.deepEqual(plan(kst("2026-11-03T17:50:00")), [{ kind: "ig", what: "cardsreel" }]);
  assert.deepEqual(plan(kst("2026-11-03T19:20:00")), [{ kind: "ig", what: "cardsreel" }]);
  assert.deepEqual(plan(kst("2026-11-03T18:00:00")), []);
});
test("토 앱 소개 릴스, 일 용어 릴스, 평일엔 주말 게시 없음", () => {
  assert.deepEqual(plan(kst("2026-11-07T11:00:00")), [{ kind: "ig", what: "reel" }]);
  assert.deepEqual(plan(kst("2026-11-08T11:40:00")), [{ kind: "ig", what: "termreel" }]);
  assert.deepEqual(plan(kst("2026-11-04T11:00:00")), []);
  assert.deepEqual(plan(kst("2026-11-11T12:00:00")), [{ kind: "ig", what: "quiz" }]);
  assert.deepEqual(plan(kst("2026-11-11T12:40:00")), [{ kind: "ig", what: "quiz" }]);
  assert.deepEqual(plan(kst("2026-11-12T12:00:00")), []);
  assert.equal(kstParts(kst("2026-11-08T11:00:00")).dow, 0);
});
