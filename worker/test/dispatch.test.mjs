import test from "node:test";
import assert from "node:assert/strict";
import { plan, kstParts } from "../src/dispatch.js";

const kst = (iso) => Date.parse(iso + "+09:00");   // 한국시간 문자열 → ms
test("평일: 16:10·16:50 데이터만, 장마감 릴스 없음", () => {
  assert.deepEqual(plan(kst("2026-11-03T16:10:00")), [{ kind: "data" }]);
  assert.deepEqual(plan(kst("2026-11-03T16:50:00")), [{ kind: "data" }]);
  assert.deepEqual(plan(kst("2026-11-03T17:50:00")), []);
  assert.deepEqual(plan(kst("2026-11-03T19:20:00")), []);
});
test("목 17:30·17:40 앱 홍보 릴스, 토 12:00·12:40 차트 퀴즈 릴스", () => {
  assert.deepEqual(plan(kst("2026-11-05T17:30:00")), [{ kind: "ig", what: "reel" }]);
  assert.deepEqual(plan(kst("2026-11-05T17:40:00")), [{ kind: "ig", what: "reel" }]);
  assert.deepEqual(plan(kst("2026-11-05T12:00:00")), []);
  assert.deepEqual(plan(kst("2026-11-07T12:00:00")), [{ kind: "ig", what: "quiz" }]);
  assert.deepEqual(plan(kst("2026-11-07T12:40:00")), [{ kind: "ig", what: "quiz" }]);
  assert.deepEqual(plan(kst("2026-11-04T12:00:00")), []);   // 수: 게시 없음
  assert.deepEqual(plan(kst("2026-11-08T12:00:00")), []);   // 일: 게시 없음
  assert.equal(kstParts(kst("2026-11-07T12:00:00")).dow, 6);
});
