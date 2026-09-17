import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../lib/client-id.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function load(crypto) {
  const context = { exports: {}, crypto, Uint8Array, Array, Date, Math };
  vm.runInNewContext(code, context);
  return context.exports.createClientId;
}

test("client identifiers use getRandomValues without randomUUID", () => {
  let seed = 0;
  const create = load({ getRandomValues(bytes) { for (let index = 0; index < bytes.length; index += 1) bytes[index] = seed + index; seed += 17; return bytes; } });
  const first = create(), second = create();
  assert.match(first, pattern);
  assert.match(second, pattern);
  assert.notEqual(first, second);
});

test("older HTTP browsers still receive distinct local identifiers", () => {
  const create = load(undefined);
  const identifiers = Array.from({ length: 20 }, () => create());
  identifiers.forEach(identifier => assert.match(identifier, pattern));
  assert.equal(new Set(identifiers).size, identifiers.length);
});
