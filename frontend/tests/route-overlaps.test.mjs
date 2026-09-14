import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../lib/route-overlaps.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { splitRouteOverlaps, offsetRouteBand } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const p = (x, y = 0) => ({ lat: y / 111195, lng: x / 111195 });
const length = (band) => band.path.slice(1).reduce((sum, point, i) => sum + Math.hypot(point.lng - band.path[i].lng, point.lat - band.path[i].lat) * 111195, 0);
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < .001, `${actual} != ${expected}`);

test("opposite traversals share one centreline with two distinct lanes", () => {
  const bands = splitRouteOverlaps([[[p(0), p(100)]], [[p(100), p(0)]]]);
  assert.equal(bands.length, 1);
  assert.deepEqual(bands[0].legs, [0, 1]);
  close(length(bands[0]), 100);
  const left = offsetRouteBand([{ x: 0, y: 0 }, { x: 100, y: 0 }], -2);
  const right = offsetRouteBand([{ x: 0, y: 0 }, { x: 100, y: 0 }], 2);
  assert.equal(left[0].y, -2); assert.equal(right[0].y, 2);
});

test("only a partially shared section is divided, preserving each leg's length", () => {
  const bands = splitRouteOverlaps([[[p(0), p(100)]], [[p(150), p(50)]]]);
  close(bands.filter((b) => b.legs.length === 2).reduce((sum, b) => sum + length(b), 0), 50);
  for (const leg of [0, 1]) close(bands.filter((b) => b.legs.includes(leg)).reduce((sum, b) => sum + length(b), 0), 100);
});

test("different sampling and API instruction boundaries do not produce seams", () => {
  const bands = splitRouteOverlaps([[[p(0), p(30)], [p(30), p(100)]], [[p(100), p(70), p(20), p(0)]]]);
  assert.equal(bands.length, 1);
  assert.deepEqual(bands[0].legs, [0, 1]);
  close(length(bands[0]), 100);
});

test("three traversals split into three bands and terminate sharing correctly", () => {
  const bands = splitRouteOverlaps([[[p(0), p(100)]], [[p(100), p(0)]], [[p(25), p(75)]]]);
  const triple = bands.filter((b) => b.legs.length === 3);
  assert.equal(triple.length, 1); close(length(triple[0]), 50);
  assert.deepEqual(triple[0].legs, [0, 1, 2]);
});

test("crossings and separate parallel roads are not labelled overlapping", () => {
  const bands = splitRouteOverlaps([[[p(0), p(100)]], [[p(50, -50), p(50, 50)]], [[p(0, 5), p(100, 5)]]]);
  assert.ok(bands.every((b) => b.legs.length === 1));
});

test("disconnected paths stay separate and inputs are not mutated", () => {
  const input = [[[p(0), p(10)], [p(90), p(100)]]];
  const before = JSON.stringify(input);
  const bands = splitRouteOverlaps(input);
  assert.equal(bands.length, 2); assert.equal(JSON.stringify(input), before);
});

test("sharp turns and duplicate vertices never create long arrow-like mitres", () => {
  const input = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 0 }, { x: 1, y: .01 }];
  const result = offsetRouteBand(input, 2);
  assert.equal(result.length, 3);
  assert.ok(result.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)));
  assert.ok(Math.hypot(result[1].x - 100, result[1].y) <= 4);
});
