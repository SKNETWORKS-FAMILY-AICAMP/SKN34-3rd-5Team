import assert from "node:assert/strict";
import { after, test } from "node:test";
import { createRequire } from "node:module";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const scratch = mkdtempSync(join(tmpdir(), "kbo-directions-route-test-"));
mkdirSync(join(scratch, "lib")); mkdirSync(join(scratch, "app", "directions-api"), { recursive: true });
for (const name of ["course-directions", "course-directions-server", "stadiums", "nearby-places", "tour-places", "tour-api", "tour-api-server", "kakao-places-server"]) {
  writeFileSync(join(scratch, "lib", `${name}.js`), ts.transpileModule(readFileSync(join(frontend, "lib", `${name}.ts`), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText);
}
const routeSource = readFileSync(join(frontend, "app", "directions-api", "route.ts"), "utf8").replaceAll('"@/lib/', '"../../lib/');
writeFileSync(join(scratch, "app", "directions-api", "route.js"), ts.transpileModule(routeSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText);
after(() => rmSync(scratch, { recursive: true }));
const requireModule = createRequire(join(scratch, "entry.cjs"));
const { POST } = requireModule("./app/directions-api/route.js");
const originalFetch = globalThis.fetch;
const originalKey = process.env.KAKAO_REST_API_KEY;
const originalTourKey = process.env.TOUR_API_KEY;
after(() => {
  globalThis.fetch = originalFetch;
  if (originalKey === undefined) delete process.env.KAKAO_REST_API_KEY; else process.env.KAKAO_REST_API_KEY = originalKey;
  if (originalTourKey === undefined) delete process.env.TOUR_API_KEY; else process.env.TOUR_API_KEY = originalTourKey;
});

const request = (body, init = {}) => new Request("http://example.test/directions-api", { method: "POST", headers: { "Content-Type": "application/json", ...init.headers }, body: typeof body === "string" ? body : JSON.stringify(body), signal: init.signal });
const place = { id: "101", place_name: "잠실 식당", road_address_name: "서울 송파구", address_name: "", category_group_name: "음식점", category_group_code: "FD6", category_name: "음식점 > 한식", phone: "", x: "127.08", y: "37.51" };
const placeBody = (overrides = {}) => ({ action: "places", method: "category", category: "FD6", lat: 37.5, lng: 127.1, radius: 2500, page: 1, size: 15, sort: "distance", ...overrides });
const walk = { status: "OK", route: { properties: { totalDistance: 100, totalTime: 60 }, legs: [{ steps: [{ path: { points: [[127.1, 37.5], [127.2, 37.6]] }, properties: { guidance: "이동" } }] }] } };

test("map data callers use POST actions without browser Places or TourAPI GET calls", () => {
  const nearby = readFileSync(join(frontend, "components", "nearby-route-planner.tsx"), "utf8");
  const routeMap = readFileSync(join(frontend, "components", "route-map.tsx"), "utf8");
  const travel = readFileSync(join(frontend, "components", "course-travel.tsx"), "utf8");
  assert.match(nearby, /action: "tourism"/); assert.doesNotMatch(nearby, /fetch\([^\n]*\/tour-api/);
  assert.match(routeMap, /searchKakaoPlaces/); assert.doesNotMatch(routeMap, /\.keywordSearch\(|\.categorySearch\(/);
  assert.match(travel, /action: "directions"/);
});

test("rejects unknown actions, non-JSON, oversized bodies and invalid place inputs", async () => {
  process.env.KAKAO_REST_API_KEY = "test-key";
  let fetches = 0;
  globalThis.fetch = async () => { fetches++; return Response.json({ meta: { is_end: true }, documents: [] }); };
  assert.equal((await POST(request({ action: "proxy", url: "https://evil.test" }))).status, 400);
  assert.equal((await POST(new Request("http://example.test/directions-api", { method: "POST", body: "{}" }))).status, 415);
  assert.equal((await POST(request("{", {}))).status, 400);
  assert.equal((await POST(request("{}", { headers: { "content-length": "12001" } }))).status, 413);
  for (const overrides of [{ category: "XX" }, { lat: 91 }, { lng: Infinity }, { radius: 0 }, { page: 4 }, { size: 16 }, { sort: "near" }, { sort: { toString: null } }, { sort: ["distance"] }, { method: { toString: null } }, { method: ["category"] }, { method: "keyword", keyword: "" }]) assert.equal((await POST(request(placeBody(overrides)))).status, 400);
  assert.equal(fetches, 0);
});

test("rejects explicitly supplied non-string actions before upstream dispatch", async () => {
  process.env.KAKAO_REST_API_KEY = "test-key";
  let fetches = 0;
  globalThis.fetch = async () => { fetches++; return Response.json(walk); };
  const points = [{ lat: 37.5, lng: 127.1 }, { lat: 37.6, lng: 127.2 }];
  for (const action of [null, { toString: null }, [], ["places"], 1, true, false]) {
    assert.equal((await POST(request({ action, mode: "walk", points }))).status, 400);
  }
  for (const action of [undefined, "directions"]) {
    for (const mode of [null, { toString: null }, [], ["walk"], 1, true, false]) {
      assert.equal((await POST(request({ ...(action === undefined ? {} : { action }), mode, points }))).status, 400);
    }
  }
  assert.equal(fetches, 0);
});

test("keeps keys server-side, fixed endpoints, zero results and sanitized upstream failures", async () => {
  delete process.env.KAKAO_REST_API_KEY;
  assert.equal((await POST(request(placeBody()))).status, 503);
  process.env.KAKAO_REST_API_KEY = "secret-key";
  let target = "";
  globalThis.fetch = async (url, options) => { target = String(url); assert.equal(options.headers.Authorization, "KakaoAK secret-key"); return Response.json({ meta: { is_end: true }, documents: [] }); };
  const empty = await POST(request(placeBody({ method: "keyword", keyword: "사직야구장", category: undefined, url: "https://evil.test" })));
  const emptyBody = await empty.json();
  assert.equal(empty.status, 200); assert.deepEqual(emptyBody, { places: [], hasNextPage: false });
  assert.equal(new URL(target).origin + new URL(target).pathname, "https://dapi.kakao.com/v2/local/search/keyword.json");
  assert.doesNotMatch(JSON.stringify(emptyBody), /secret-key/);
  globalThis.fetch = async () => new Response("credential-bearing error", { status: 503 });
  const failed = await POST(request(placeBody({ lat: 37.6 })));
  assert.equal(failed.status, 502); assert.doesNotMatch(await failed.text(), /credential|secret/);
});

test("preserves legacy directions, supports explicit directions and missing optional tourism key", async () => {
  process.env.KAKAO_REST_API_KEY = "test-key";
  delete process.env.TOUR_API_KEY;
  globalThis.fetch = async () => Response.json(walk);
  const points = [{ lat: 37.5, lng: 127.1 }, { lat: 37.6, lng: 127.2 }];
  for (const body of [{ mode: "walk", points }, { action: "directions", mode: "walk", points }]) {
    const response = await POST(request(body));
    assert.equal(response.status, 200); assert.equal((await response.json()).legs[0].status, "ok");
  }
  const tourism = await POST(request({ action: "tourism", stadium: "JAMSIL", lat: 37.5161987797456, lng: 127.075940589715 }));
  assert.equal(tourism.status, 200); assert.deepEqual(await tourism.json(), { status: "unconfigured", places: [], truncated: false });
});

test("place quota accepts a normal 18-search three-page fan-out and bounds concurrency", async () => {
  process.env.KAKAO_REST_API_KEY = "test-key";
  globalThis.fetch = async () => Response.json({ meta: { is_end: false }, documents: [place] });
  for (let index = 0; index < 54; index++) assert.equal((await POST(request(placeBody({ lat: 36 + index / 1000 })))).status, 200);

  const releases = [];
  globalThis.fetch = (_, options) => new Promise((resolve, reject) => {
    releases.push(() => resolve(Response.json({ meta: { is_end: true }, documents: [] })));
    options.signal.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")), { once: true });
  });
  const pending = Array.from({ length: 9 }, (_, index) => POST(request(placeBody({ lat: 35 + index / 1000 }))));
  await new Promise((resolve) => setImmediate(resolve));
  releases.forEach((release) => release());
  const statuses = await Promise.all(pending).then((responses) => responses.map((response) => response.status));
  assert.equal(statuses.filter((status) => status === 200).length, 8);
  assert.equal(statuses.filter((status) => status === 429).length, 1);
});

test("aborted and timed-out place upstream requests return sanitized failures", async () => {
  process.env.KAKAO_REST_API_KEY = "test-key";
  globalThis.fetch = (_, options) => new Promise((_, reject) => {
    const fail = () => reject(new DOMException("cancelled secret URL", "AbortError"));
    if (options.signal.aborted) fail(); else options.signal.addEventListener("abort", fail, { once: true });
  });
  const controller = new AbortController();
  const pending = POST(request(placeBody({ lat: 34.5 }), { signal: controller.signal }));
  controller.abort();
  const response = await pending;
  assert.equal(response.status, 502); assert.doesNotMatch(await response.text(), /secret URL/);
  globalThis.fetch = async () => { throw new DOMException("credential URL timed out", "TimeoutError"); };
  const timedOut = await POST(request(placeBody({ lat: 34.6 })));
  assert.equal(timedOut.status, 502); assert.doesNotMatch(await timedOut.text(), /credential URL/);
});
