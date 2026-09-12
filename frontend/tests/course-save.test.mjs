import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";

const source = readFileSync(new URL("../lib/routes.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } });

function storageHarness() {
  const storage = new Map();
  let blocked = false;
  const browser = {
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => { if (blocked) throw new Error("quota"); storage.set(key, value); },
    },
    dispatchEvent() {},
  };
  const testModule = { exports: {} };
  new Function("require", "module", "exports", "window", outputText)(createRequire(import.meta.url), testModule, testModule.exports, browser);
  return { ...testModule.exports, block: () => { blocked = true; } };
}

const course = (id) => ({
  id, title: "잠실 직관 코스", stadium: "잠실야구장", description: "출발지 → 카페", content: "",
  tags: [], duration: "반나절", cover: "/images/stadium-night.jpg", author: "나의 코스", likes: 0,
  isSample: false, createdAt: "2026-09-12T12:00:00.000Z",
  stops: [{ name: "카페", category: "카페", placeId: "123", lat: 37.51, lng: 127.07 }],
});

test("a named course without a story persists its visits and separate start coordinates", () => {
  const api = storageHarness();
  const route = { ...course("local-one"), start: { lat: 37.516, lng: 127.075 } };
  api.saveRoute(route);
  assert.deepEqual(api.getRoutes().find((item) => item.id === route.id), route);
});

test("editing updates one course and keeps other courses and legacy routes intact", () => {
  const api = storageHarness();
  const first = course("local-one"), second = course("local-two");
  api.saveRoute(first); api.saveRoute(second);
  api.saveRoute({ ...first, title: "새 코스 이름", start: { lat: 37.52, lng: 127.08 } });
  assert.equal(api.getRoutes().filter((item) => item.id === first.id).length, 1);
  assert.equal(api.getRoutes().find((item) => item.id === first.id).title, "새 코스 이름");
  assert.deepEqual(api.getRoutes().find((item) => item.id === second.id), second);
});

test("invalid start coordinates cannot replace a previously saved course", () => {
  const api = storageHarness();
  const original = course("local-one");
  api.saveRoute(original);
  for (const start of [null, {}, { lat: NaN, lng: 127 }, { lat: 91, lng: 127 }, { lat: "37.5", lng: 127 }]) {
    assert.throws(() => api.saveRoute({ ...original, start }));
    assert.deepEqual(api.getRoutes().find((item) => item.id === original.id), original);
  }
});

test("storage failure is reported and leaves the previous course available", () => {
  const api = storageHarness();
  const original = course("local-one");
  api.saveRoute(original); api.block();
  assert.throws(() => api.saveRoute({ ...original, title: "저장 실패" }), /저장/);
  assert.deepEqual(api.getRoutes().find((item) => item.id === original.id), original);
});
