import assert from "node:assert/strict";
import { after, test } from "node:test";
import { createRequire } from "node:module";
import { mkdtempSync, readFileSync, rmdirSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const scratch = mkdtempSync(join(tmpdir(), "kbo-directions-test-"));
const modules = ["course-directions", "course-directions-server"];
for (const name of modules) writeFileSync(join(scratch, `${name}.js`), ts.transpileModule(readFileSync(join(frontend, "lib", `${name}.ts`), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText);
after(() => { for (const name of modules) unlinkSync(join(scratch, `${name}.js`)); rmdirSync(scratch); });
const require = createRequire(join(scratch, "entry.cjs"));
const { parseCourseRequest, parseDirections, fetchCourseDirections } = require("./course-directions-server.js");
const { travelTime } = require("./course-directions.js");
const step = { path: { points: [[127.1, 37.5], [127.2, 37.6]] }, properties: { guidance: "횡단보도를 건너세요" } };
const walk = (seconds = 70) => ({ status: "OK", route: { properties: { totalDistance: 100, totalTime: seconds }, legs: [{ steps: [step] }] } });

test("validate mode, numeric coordinates and up to 12 stops plus current location", () => {
  const point = { lat: 37.5, lng: 127.1 };
  assert.ok(parseCourseRequest({ mode: "walk", points: Array(13).fill(point) }));
  for (const input of [null, {}, { mode: "fly", points: [point, point] }, { mode: "walk", points: [point] }, { mode: "car", points: Array(14).fill(point) }, { mode: "walk", points: [point, { lat: "37", lng: 127 }] }, { mode: "walk", points: [point, { lat: 91, lng: 127 }] }]) assert.equal(parseCourseRequest(input), null);
});
test("walking uses provider seconds and actual coordinates, not straight-line estimates", () => {
  const result = parseDirections("walk", walk());
  assert.equal(result.seconds, 70);
  assert.equal(result.distance, 100);
  assert.deepEqual(result.paths[0][0], { lat: 37.5, lng: 127.1 });
  assert.equal(result.instructions[0], "횡단보도를 건너세요");
  assert.equal(travelTime(70), "2분");
  assert.equal(travelTime(3601), "1시간 1분");
});
test("transit selects the fastest valid alternative and preserves separate step geometry", () => {
  const route = (time) => ({ properties: { totalTime: time, totalDistance: 500 }, steps: [step, step] });
  const result = parseDirections("transit", { status: "OK", routes: [route(1000), route(450)] });
  assert.equal(result.seconds, 450);
  assert.equal(result.paths.length, 2);
});
test("car decodes alternating longitude/latitude road vertices", () => {
  const result = parseDirections("car", { routes: [{ result_code: 0, summary: { duration: 300, distance: 850 }, sections: [{ roads: [{ name: "올림픽로", vertexes: [127.1, 37.5, 127.2, 37.6] }] }] }] });
  assert.equal(result.seconds, 300);
  assert.deepEqual(result.paths[0], [{ lat: 37.5, lng: 127.1 }, { lat: 37.6, lng: 127.2 }]);
});
test("missing routes, invalid totals and missing geometry cannot appear as successful estimates", () => {
  for (const value of [{ status: "NO_RESULTS" }, {}, walk(-1), { status: "OK", route: { properties: { totalDistance: 100, totalTime: 60 }, legs: [] } }]) assert.throws(() => parseDirections("walk", value));
  assert.throws(() => parseDirections("car", { routes: [{ result_code: 104 }] }));
  assert.equal(parseDirections("walk", { status: "SAME_POINT" }).seconds, 0);
});
test("12 legs preserve course order, use only requested mode, and have bounded concurrency", async () => {
  const points = Array.from({ length: 13 }, (_, i) => ({ lat: 36 + i / 100, lng: 128 }));
  let active = 0, maxActive = 0;
  const calls = [];
  const fetcher = async (url, options) => {
    active++; maxActive = Math.max(maxActive, active); calls.push(url);
    assert.equal(options.headers.Authorization, "KakaoAK test-key");
    assert.equal(new URL(url).pathname, "/v2/routing/walk");
    await new Promise((resolve) => setTimeout(resolve, 2)); active--;
    const i = Math.round((Number(new URL(url).searchParams.get("start_y")) - 36) * 100);
    return Response.json(walk(i + 1));
  };
  const result = await fetchCourseDirections("walk", points, "test-key", fetcher);
  assert.equal(calls.length, 12); assert.ok(maxActive <= 3);
  assert.deepEqual(result.legs.map((leg) => leg.seconds), Array.from({ length: 12 }, (_, i) => i + 1));
  assert.equal(result.seconds, 78); assert.equal(result.distance, 1200);
});
test("partial failures do not report a misleading whole-course total or expose upstream errors", async () => {
  let calls = 0;
  const result = await fetchCourseDirections("walk", [{ lat: 35, lng: 127 }, { lat: 35.1, lng: 127 }, { lat: 35.2, lng: 127 }], "secret", async () => {
    if (++calls === 1) return Response.json(walk());
    throw new Error("provider URL with secret");
  });
  assert.equal(result.seconds, null); assert.equal(result.distance, null);
  assert.equal(result.legs[0].status, "ok"); assert.equal(result.legs[1].status, "error");
  assert.ok(!JSON.stringify(result).includes("secret"));
});
test("identical adjacent coordinates avoid unnecessary requests", async () => {
  const p = { lat: 37, lng: 127 };
  const result = await fetchCourseDirections("walk", [p, p], "test", async () => { throw new Error("must not call"); });
  assert.equal(result.seconds, 0); assert.equal(result.legs[0].status, "ok");
});
