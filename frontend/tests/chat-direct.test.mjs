import assert from "node:assert/strict";
import { after, beforeEach, test } from "node:test";
import { createRequire } from "node:module";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const scratch = mkdtempSync(join(tmpdir(), "kbo-chat-direct-test-"));
after(() => rmSync(scratch, { recursive: true, force: true }));
for (const name of ["lib/member-auth-request", "lib/chat/types", "lib/chat/validation", "lib/chat/client"]) {
  const source = readFileSync(join(frontend, `${name}.ts`), "utf8");
  const { outputText } = ts.transpileModule(source, {
    fileName: `${name}.ts`, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  });
  mkdirSync(dirname(join(scratch, `${name}.js`)), { recursive: true });
  writeFileSync(join(scratch, `${name}.js`), outputText);
}

global.window = { setTimeout, clearTimeout };
const stored = new Map();
global.sessionStorage = {
  getItem: key => stored.get(key) ?? null,
  setItem: (key, value) => stored.set(key, value),
  removeItem: key => stored.delete(key),
};
const require = createRequire(join(scratch, "entry.cjs"));
const { clearMemberTokens, saveMemberTokens } = require("./lib/member-auth-request.js");
const { ChatClientError, getChatStatus, sendChatMessage, sendGuestChatMessage } = require("./lib/chat/client.js");
const json = (value, status = 200) => Response.json(value, { status });
const sse = events => new Response(new ReadableStream({
  start(controller) {
    controller.enqueue(new TextEncoder().encode(events.map(([event, data]) =>
      `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`).join("")));
    controller.close();
  },
}), { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
const memberEvents = (turn = "turn-1", chunks = ["첫 ", "답변"]) => [
  ["checkpoint", { turn_id: turn, receipt: "empty" }],
  ...chunks.map((text, index) => ["delta", { turn_id: turn, receipt: `part-${index}`, text }]),
  ["done", { turn_id: turn, receipt: "complete" }],
];

beforeEach(() => { stored.clear(); clearMemberTokens(); });

test("member completion uses protected direct endpoints and observable finalize ids", async () => {
  saveMemberTokens("access-token", "refresh-token");
  const calls = [];
  global.fetch = async (url, init = {}) => {
    const body = init.body && JSON.parse(init.body);
    calls.push({ url: String(url), method: init.method, body, authorization: new Headers(init.headers).get("Authorization") });
    if (init.method === "GET") return json([]);
    if (String(url) === "/api/chat/sessions/") return json({ id: 7 }, 201);
    if (String(url).includes("/finalize/")) return json({
      turn_id: "turn-1", session_id: 7, status: body.status,
      user_message_id: 11, assistant_message_id: 12, assistant_message: body.prefix,
    });
    return sse(memberEvents());
  };
  assert.equal((await getChatStatus()).provider, "backend");
  const seen = [];
  const reply = await sendChatMessage(
    { messages: [{ role: "user", content: "첫 질문" }] }, undefined,
    { onDelta: value => seen.push(value) },
  );
  assert.deepEqual(seen, ["첫 ", "첫 답변"]);
  assert.deepEqual(
    { reply: reply.reply, status: reply.completionStatus, user: reply.userMessageId, assistant: reply.assistantMessageId },
    { reply: "첫 답변", status: "completed", user: 11, assistant: 12 },
  );
  assert.deepEqual(calls.map(call => [call.method, call.url]), [
    ["GET", "/api/chat/sessions/"], ["POST", "/api/chat/sessions/"],
    ["POST", "/api/chat/sessions/7/messages/"], ["POST", "/api/chat/turns/turn-1/finalize/"],
  ]);
  assert.ok(calls.every(call => call.authorization === "Bearer access-token"));
});

test("member Stop freezes the last received signed prefix and is not an error", async () => {
  saveMemberTokens("access-token", "refresh-token");
  const controller = new AbortController();
  let latest = null, frozen = null, finalized;
  global.fetch = async (url, init = {}) => {
    if (String(url).includes("/finalize/")) {
      finalized = JSON.parse(init.body);
      return json({ turn_id: "turn-stop", session_id: 9, status: "stopped", user_message_id: 21, assistant_message_id: 22, assistant_message: finalized.prefix });
    }
    return new Response(new ReadableStream({
      start(stream) {
        stream.enqueue(new TextEncoder().encode(
          'event: checkpoint\ndata: {"turn_id":"turn-stop","receipt":"empty"}\n\n' +
          'event: delta\ndata: {"turn_id":"turn-stop","receipt":"signed-partial","text":"정확한 부분"}\n\n'));
        init.signal.addEventListener("abort", () => stream.error(new DOMException("Aborted", "AbortError")), { once: true });
      },
    }), { headers: { "Content-Type": "text/event-stream" } });
  };
  const reply = await sendChatMessage(
    { sessionId: 9, messages: [{ role: "user", content: "질문" }] }, controller.signal,
    {
      onCheckpoint: checkpoint => { latest = checkpoint; },
      onDelta: () => { frozen = latest; controller.abort(); },
      getStop: () => frozen,
    },
  );
  assert.equal(reply.completionStatus, "stopped");
  assert.equal(reply.reply, "정확한 부분");
  assert.deepEqual(finalized, { receipt: "signed-partial", prefix: "정확한 부분", status: "stopped" });
});

test("member Stop requested before the initial checkpoint persists only the human message", async () => {
  saveMemberTokens("access-token", "refresh-token");
  const controller = new AbortController();
  let frozen = null, finalized;
  global.fetch = async (url, init = {}) => {
    if (String(url) === "/api/chat/sessions/") return json({ id: 10 }, 201);
    if (String(url).includes("/finalize/")) {
      finalized = JSON.parse(init.body);
      return json({ turn_id: "turn-empty", session_id: 10, status: "stopped", user_message_id: 31, assistant_message_id: null, assistant_message: "" });
    }
    return new Response(new ReadableStream({
      start(stream) {
        stream.enqueue(new TextEncoder().encode('event: checkpoint\ndata: {"turn_id":"turn-empty","receipt":"signed-empty"}\n\n'));
        init.signal.addEventListener("abort", () => stream.error(new DOMException("Aborted", "AbortError")), { once: true });
      },
    }), { headers: { "Content-Type": "text/event-stream" } });
  };
  const reply = await sendChatMessage(
    { messages: [{ role: "user", content: "질문" }] }, controller.signal,
    {
      onCheckpoint: checkpoint => { frozen = checkpoint; controller.abort(); },
      getStop: () => frozen,
    },
  );
  assert.equal(reply.completionStatus, "stopped");
  assert.equal(reply.reply, "");
  assert.equal(reply.assistantMessageId, null);
  assert.deepEqual(finalized, { receipt: "signed-empty", prefix: "", status: "stopped" });
});

test("member finalize failure reports uncertainty without losing the received answer", async () => {
  saveMemberTokens("access-token", "refresh-token");
  let received = "";
  global.fetch = async (url) => String(url).includes("/finalize/")
    ? json({ detail: "save unavailable" }, 500)
    : sse(memberEvents("turn-unsaved", ["받은 ", "전체 답변"]));
  await assert.rejects(
    sendChatMessage(
      { sessionId: 11, messages: [{ role: "user", content: "질문" }] },
      undefined,
      { onDelta: answer => { received = answer; } },
    ),
    error => error instanceof ChatClientError && error.uncertain,
  );
  assert.equal(received, "받은 전체 답변");
});

test("guest uses bounded browser history, Stop before a token stays local, and no auth header is sent", async () => {
  const controller = new AbortController();
  let frozen = null, body, authorization;
  global.fetch = async (url, init = {}) => {
    assert.equal(url, "/api/chat/guest/");
    body = JSON.parse(init.body); authorization = new Headers(init.headers).get("Authorization");
    return new Response(new ReadableStream({
      start(stream) { init.signal.addEventListener("abort", () => stream.error(new DOMException("Aborted", "AbortError")), { once: true }); },
    }), { headers: { "Content-Type": "text/event-stream" } });
  };
  const reply = await sendGuestChatMessage(
    { messages: [{ role: "user", content: "이전 질문" }, { role: "assistant", content: "부분" }, { role: "user", content: "후속" }] },
    controller.signal,
    {
      onCheckpoint: checkpoint => { frozen = checkpoint; controller.abort(); },
      getStop: () => frozen,
    },
  );
  assert.deepEqual(body.messages.map(item => item.content), ["이전 질문", "부분", "후속"]);
  assert.equal(authorization, null);
  assert.equal(reply.completionStatus, "stopped");
  assert.equal(reply.reply, "");
});

test("guest read failure is retryable while failed member auth never falls back to guest", async () => {
  global.fetch = async url => {
    if (String(url) === "/api/chat/guest/") return new Response("broken", { headers: { "Content-Type": "text/plain" } });
    throw new Error("guest fallback must not be attempted");
  };
  await assert.rejects(sendGuestChatMessage({ messages: [{ role: "user", content: "질문" }] }), error => error instanceof ChatClientError && !error.uncertain);
  await assert.rejects(getChatStatus(), error => error instanceof ChatClientError && error.status === 401);
});

test("provider clears guest/member state on every identity switch and renders explicit Stop", () => {
  const provider = readFileSync(join(frontend, "components/chat-provider.tsx"), "utf8");
  const surfaces = ["components/chat-popup.tsx", "components/chat-workspace.tsx"].map(path => readFileSync(join(frontend, path), "utf8"));
  assert.match(provider, /const identity = memberStatus === "authenticated"/);
  for (const cleanup of ["controller.abort()", "backendSessions.current.clear()", "archivedConversations.current.clear()", "historyRef.current = []", "streamingRef.current = \"\""]) assert.ok(provider.includes(cleanup));
  assert.match(provider, /mode === "member" \? sendChatMessage : sendGuestChatMessage/);
  assert.match(provider, /deliveryUncertain = mode === "member"/);
  assert.match(provider, /active\.wantsStop = true;[\s\S]*?if \(active\.checkpoint\)/);
  assert.match(provider, /if \(active\.wantsStop && !active\.stop\) \{ active\.stop = checkpoint; controller\.abort\(\); \}/);
  assert.match(provider, /finalizeSignal: identityController\.signal/);
  assert.doesNotMatch(provider, /localStorage|sessionStorage/);
  assert.match(provider, /messages: identityChanged \? \[\] : messages/);
  assert.match(provider, /setMessages\(\[\.\.\.previous, userMessage, \{ role: "assistant", content: received \}\]\)/);
  assert.match(provider, /받은 답변은 저장되지 않았어요/);
  for (const surface of surfaces) {
    assert.match(surface, /답변 생성 중단/);
    assert.match(surface, /게스트 대화/);
    assert.match(surface, /aria-relevant="additions"/);
  }
});
