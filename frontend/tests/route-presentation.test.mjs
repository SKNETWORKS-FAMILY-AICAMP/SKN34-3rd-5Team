import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../lib/route-presentation.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { directionMarker } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const view = { left: 0, top: 0, right: 600, bottom: 400 };
const point = (x, y = 200) => ({ x, y, lat: y / 1000, lng: x / 1000 });

test("dense geometry still yields one marker on the original route", () => {
  const path = Array.from({ length: 101 }, (_, i) => point(50 + i * 5));
  const marker = directionMarker([path], view, [], []);
  assert.ok(marker);
  assert.equal(marker.angle, 0);
  assert.equal(marker.y, 200);
  assert.ok(Math.abs(marker.lng * 1000 - marker.x) < .00001);
});

test("return journey points the opposite way", () => {
  const marker = directionMarker([[point(550), point(50)]], view, [], []);
  assert.equal(Math.abs(marker.angle), Math.PI);
});

test("markers avoid stop pins and other direction markers", () => {
  const stops = [point(300)], used = [point(180)];
  const marker = directionMarker([[point(50), point(550)]], view, stops, used);
  assert.ok(marker);
  assert.ok(Math.abs(marker.x - 300) >= 44);
  assert.ok(Math.abs(marker.x - 180) >= 140);
});

test("offscreen and disconnected short paths do not get invented arrows", () => {
  assert.equal(directionMarker([[point(10, -100), point(500, -100)]], view, [], []), undefined);
  assert.equal(directionMarker([[point(100), point(110)], [point(500), point(510)]], view, [], []), undefined);
});
