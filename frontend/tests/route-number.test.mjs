import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../lib/route-number.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const require = createRequire(import.meta.url);
function harness() {
  let raw = null;
  let blocked = false;
  let queue = Promise.resolve();
  const storage = { getItem: () => raw, setItem: (_, value) => { if (blocked) throw new Error("Storage full"); raw = value; } };
  const locks = { request: (_, callback) => { const next = queue.then(callback); queue = next.catch(() => {}); return next; } };
  const load = () => {
    const context = { exports: {}, require, navigator: { locks }, window: { localStorage: storage, dispatchEvent() {} }, Event };
    vm.runInNewContext(code, context);
    return context.exports.ensureLocalRouteNumber;
  };
  return { load, block: () => { blocked = true; }, replace: value => { raw = value; } };
}

test("route numbers remain stable after reload and distinct from other routes", async () => {
  const h = harness(); const allocate = h.load();
  assert.equal(await allocate("jamsil-day"), "000001");
  assert.equal(await allocate("route-a"), "000007");
  assert.equal(await allocate("route-b"), "000008");
  assert.equal(await h.load()("route-a"), "000007");
  assert.equal(await h.load()("route-c"), "000009");
});
test("concurrent tab allocations use one registry without duplicate numbers", async () => {
  const h = harness(); const first = h.load(); const second = h.load();
  const numbers = await Promise.all([first("a"), second("b"), second("a")]);
  assert.deepEqual(numbers, ["000007", "000008", "000007"]);
});
test("storage failure never returns an unpersisted number", async () => {
  const h = harness(); h.block();
  await assert.rejects(h.load()("new-route"), /Storage full/);
});
test("damaged or exhausted registries never reset and reuse numbers", async () => {
  const h = harness();
  h.replace("broken"); await assert.rejects(h.load()("new-route"));
  h.replace(JSON.stringify({ last: 8, entries: { a: "000007", b: "000007" } }));
  await assert.rejects(h.load()("new-route"));
  h.replace(JSON.stringify({ last: 999999, entries: {} }));
  await assert.rejects(h.load()("new-route"), /exhausted/);
});
