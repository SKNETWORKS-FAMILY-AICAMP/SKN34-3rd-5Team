import assert from "node:assert/strict";
import { after, beforeEach, test } from "node:test";
import { createRequire } from "node:module";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const scratch = mkdtempSync(join(tmpdir(), "kbo-auth-bridge-"));
after(() => rmSync(scratch, { recursive: true, force: true }));
for (const name of ["server-only", "next"]) mkdirSync(join(scratch, "node_modules", name), { recursive: true });
writeFileSync(join(scratch, "node_modules/server-only/index.js"), "module.exports = {};\n");
writeFileSync(join(scratch, "node_modules/next/headers.js"), `
const values = new Map();
exports.values = values;
exports.cookies = async () => ({
  get: name => values.has(name) ? { value: values.get(name) } : undefined,
  has: name => values.has(name),
  set: (name, value) => values.set(name, value),
  delete: name => values.delete(name),
});
`);
mkdirSync(join(scratch, "chat"));
for (const name of ["team-backend", "member-auth-request", "chat/validation", "chat/types"]) {
  const source = readFileSync(join(root, "lib", `${name}.ts`), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } });
  writeFileSync(join(scratch, `${name}.js`), outputText);
}
const require = createRequire(join(scratch, "test.cjs"));
const sessionValues = new Map();
global.sessionStorage = { getItem: name => sessionValues.get(name) ?? null, setItem: (name, value) => sessionValues.set(name, value), removeItem: name => sessionValues.delete(name) };
const cookieValues = require("next/headers").values;
const { clearTokens, saveTokens, teamRequest } = require("./team-backend.js");
const { clearMemberTokens, createMemberRequestGate, isCurrentMember, loadLatestMember, logoutMember, memberFetch, normalizeMemberEmail, saveMemberTokens } = require("./member-auth-request.js");
beforeEach(() => { cookieValues.clear(); clearMemberTokens(); process.env.CHAT_BACKEND_URL = "http://backend:8000/"; });

test("auth callers use the backend-shaped public paths", () => {
  const sources = ["app/login/page.tsx", "app/signup/page.tsx", "app/mypage/page.tsx", "components/member-account-settings.tsx", "components/member-header-actions.tsx", "lib/member-auth-request.ts"].map(name => readFileSync(join(root, name), "utf8")).join("\n");
  for (const path of ["/api/auth/signin", "/api/auth/signup/", "/api/auth/user", "/api/auth/logout", "/api/auth/username/request", "/api/auth/password/request", "/api/auth/password", "/api/auth/email/request", "/api/auth/email/verify"]) assert.match(sources, new RegExp(path.replaceAll("/", "\\/")));
  assert.doesNotMatch(sources, /\/team-auth\//);
  assert.match(sources, /\/api\/auth\/token\/refresh\//);
  assert.match(readFileSync(join(root, "app/signup/page.tsx"), "utf8"), /re_password: values\.passwordConfirm/);
  assert.doesNotMatch(readFileSync(join(root, "lib/member-auth-request.ts"), "utf8"), /localStorage/);
});

test("nginx sends every API path directly to Django", () => {
  const nginx = readFileSync(join(root, "..", "nginx", "nginx.conf"), "utf8");
  assert.match(nginx, /location \/api\/\s*\{[\s\S]*?proxy_pass http:\/\/backend:8000\//);
  assert.doesNotMatch(nginx, /location \^~ \/api\/auth/);
});

test("an expired access token performs one direct refresh and one retry", async () => {
  saveMemberTokens("expired-access", "refresh-token");
  const calls = [];
  global.fetch = async (url, init) => {
    calls.push({ url: String(url), authorization: new Headers(init?.headers).get("Authorization"), body: init?.body });
    if (String(url) === "/api/auth/token/refresh/") return Response.json({ access: "new-access" });
    if (calls.filter(call => call.url === "/api/auth/user").length === 1) return Response.json({ detail: "만료" }, { status: 401 });
    return Response.json({ id: 1 });
  };
  assert.equal((await memberFetch("/api/auth/user")).status, 200);
  assert.equal(calls.filter(call => call.url === "/api/auth/token/refresh/").length, 1);
  assert.equal(calls.at(-1).authorization, "Bearer new-access");
  assert.deepEqual(JSON.parse(calls[1].body), { refresh: "refresh-token" });
});

test("concurrent 401 retries share refresh without sending Bearer null", async () => {
  saveMemberTokens("expired-access", "refresh-token");
  const authorizations = [];
  let userCalls = 0;
  global.fetch = async (url, init) => {
    if (String(url) === "/api/auth/token/refresh/") return Response.json({ access: "new-access" });
    authorizations.push(new Headers(init?.headers).get("Authorization"));
    userCalls += 1;
    return userCalls <= 2 ? Response.json({ detail: "만료" }, { status: 401 }) : Response.json({ id: 1 });
  };
  assert.deepEqual(await Promise.all([memberFetch("/api/auth/user"), memberFetch("/api/auth/user")]).then(responses => responses.map(response => response.status)), [200, 200]);
  assert.equal(authorizations.includes("Bearer null"), false);
  assert.deepEqual(authorizations.slice(-2), ["Bearer new-access", "Bearer new-access"]);
});

test("a delayed member refresh cannot restore tokens after logout", async () => {
  saveMemberTokens("expired-access", "refresh-token");
  let finishRefresh;
  const refreshResponse = new Promise(resolve => { finishRefresh = resolve; });
  const calls = [];
  global.fetch = async (url, init) => {
    calls.push({ url: String(url), authorization: new Headers(init?.headers).get("Authorization") });
    if (String(url) === "/api/auth/token/refresh/") return refreshResponse;
    if (String(url) === "/api/auth/logout") return new Response(null, { status: 200 });
    return Response.json({ detail: "만료" }, { status: 401 });
  };
  const pending = memberFetch("/api/auth/user");
  await new Promise(resolve => setTimeout(resolve));
  assert.equal((await logoutMember()).status, 200);
  finishRefresh(Response.json({ access: "late-access", refresh: "late-refresh" }));
  assert.equal((await pending).status, 401);
  assert.equal(sessionStorage.getItem("kbo_refresh"), null);
  assert.equal(calls.some(call => call.authorization === "Bearer late-access"), false);
});

test("a delayed member refresh cannot overwrite a newer login", async () => {
  saveMemberTokens("expired-access", "old-refresh");
  let finishRefresh;
  const refreshResponse = new Promise(resolve => { finishRefresh = resolve; });
  const calls = [];
  global.fetch = async (url, init) => {
    calls.push({ url: String(url), authorization: new Headers(init?.headers).get("Authorization") });
    if (String(url) === "/api/auth/token/refresh/") return refreshResponse;
    if (calls.filter(call => call.url === "/api/auth/user").length === 1) return Response.json({ detail: "만료" }, { status: 401 });
    return Response.json({ id: 1 });
  };
  const pending = memberFetch("/api/auth/user");
  await new Promise(resolve => setTimeout(resolve));
  saveMemberTokens("new-login-access", "new-login-refresh");
  finishRefresh(Response.json({ access: "late-access", refresh: "late-refresh" }));
  assert.equal((await pending).status, 200);
  assert.equal(sessionStorage.getItem("kbo_refresh"), "new-login-refresh");
  assert.equal(calls.at(-1).authorization, "Bearer new-login-access");
});

test("logout sends the refresh token to Django then clears tab storage", async () => {
  saveMemberTokens("access-token", "refresh-token");
  let request;
  global.fetch = async (url, init) => { request = { url: String(url), body: JSON.parse(init.body) }; return new Response(null, { status: 200 }); };
  assert.equal((await logoutMember()).status, 200);
  assert.deepEqual(request, { url: "/api/auth/logout", body: { refresh: "refresh-token" } });
  assert.equal(sessionStorage.getItem("kbo_refresh"), null);
});

test("empty 201 and 204 backend successes are valid", async () => {
  global.fetch = async () => new Response(null, { status: 201 });
  assert.equal(await teamRequest("auth/signup/", {}, false), null);
  global.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await teamRequest("auth/logout", {}, false), null);
});

test("DRF field errors retain status and safe fields", async () => {
  global.fetch = async () => Response.json({ username: ["이미 사용 중입니다."] }, { status: 400 });
  await assert.rejects(teamRequest("auth/signup/", {}, false), error => error.status === 400 && error.fields.username[0] === "이미 사용 중입니다.");
});

test("logout marker blocks a late refreshed access cookie until a real login", async () => {
  await clearTokens();
  cookieValues.set("kbo_access", "late-access");
  let called = false;
  global.fetch = async () => { called = true; return Response.json({}); };
  await assert.rejects(teamRequest("auth/user", undefined, true, undefined, "GET"), error => error.status === 401);
  assert.equal(called, false);
  await saveTokens("new-access", "new-refresh", true);
  assert.equal(cookieValues.has("kbo_logged_out"), false);
});

test("an in-flight refresh finishing after logout preserves the logout marker", async () => {
  cookieValues.set("kbo_refresh", "refresh-token");
  let finishRefresh;
  const refreshResponse = new Promise(resolve => { finishRefresh = resolve; });
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    if (calls === 1) return refreshResponse;
    return Response.json({ id: 1 });
  };
  const pending = teamRequest("auth/user", undefined, true, undefined, "GET");
  await new Promise(resolve => setTimeout(resolve));
  await clearTokens();
  finishRefresh(Response.json({ access: "late-access", refresh: "late-refresh" }));
  await pending;
  assert.equal(cookieValues.has("kbo_logged_out"), true);
});

test("a delayed identity response cannot overwrite an explicit anonymous state", async () => {
  const gate = createMemberRequestGate();
  let finish;
  const response = new Promise(resolve => { finish = resolve; });
  let state = { status: "loading", user: null };
  const pending = loadLatestMember(gate, () => response).then(next => { if (next) state = next; });
  gate.invalidate();
  state = { status: "anonymous", user: null };
  finish(Response.json({ id: 1, username: "late-user" }));
  await pending;
  assert.deepEqual(state, { status: "anonymous", user: null });
});

test("identity timeout becomes server unavailable", async () => {
  const gate = createMemberRequestGate(5);
  const result = await loadLatestMember(gate, signal => new Promise((_, reject) => signal.addEventListener("abort", () => reject(new DOMException("timed out", "AbortError")))));
  assert.deepEqual(result, { status: "unavailable", user: null });
});

test("a delayed profile write cannot recreate a logged-out member", async () => {
  let current = { id: 1, username: "member" };
  let finish;
  const response = new Promise(resolve => { finish = resolve; });
  const pending = response.then(user => { if (isCurrentMember(current, 1)) current = user; });
  current = null;
  finish({ id: 1, username: "late-member" });
  await pending;
  assert.equal(current, null);
});

test("email comparison normalizes uppercase input", () => {
  assert.equal(normalizeMemberEmail("  USER@Example.COM  "), "user@example.com");
});
