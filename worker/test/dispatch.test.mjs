import test from "node:test";
import assert from "node:assert/strict";
import { plan, kstParts } from "../src/dispatch.js";

const kst = (iso) => Date.parse(iso + "+09:00");   // 한국시간 문자열 → ms
test("평일: 16:10·16:50 데이터만, 장마감 릴스 없음", () => {
  assert.deepEqual(plan(kst("2026-11-03T16:10:00")), [{ kind: "data" }]);
  assert.deepEqual(plan(kst("2026-11-03T16:50:00")), [{ kind: "data" }]);
  assert.deepEqual(plan(kst("2026-11-03T19:20:00")), []);
  assert.deepEqual(plan(kst("2026-11-03T06:40:00")), [{ kind: "data", force: true }]);   // 아침 갱신
  assert.deepEqual(plan(kst("2026-11-08T06:40:00")), []);                                  // 주말은 없음
  assert.deepEqual(plan(kst("2026-11-03T07:10:00")), [{ kind: "report", slot: "am" }]);
  assert.deepEqual(plan(kst("2026-11-03T16:40:00")), [{ kind: "report", slot: "pm" }]);
});
test("월·수·금 17:30·17:40 그날의 기록 릴스, 주식연구소 릴스는 중단", () => {
  assert.deepEqual(plan(kst("2026-11-02T17:30:00")), [{ kind: "hreel" }]);   // 월
  assert.deepEqual(plan(kst("2026-11-04T17:40:00")), [{ kind: "hreel" }]);   // 수
  assert.deepEqual(plan(kst("2026-11-06T17:30:00")), [{ kind: "hreel" }]);   // 금
  assert.deepEqual(plan(kst("2026-11-03T17:30:00")), []);                    // 화: 없음
  assert.deepEqual(plan(kst("2026-11-07T12:00:00")), []);                    // 토: 없음
  assert.equal(kstParts(kst("2026-11-07T12:00:00")).dow, 6);
});
