import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../lib/youtube/playback.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
});

function harness(preview = true) {
  const children = [];
  const calls = [];
  const statuses = [];
  const timers = new Map();
  let events;
  const target = { destroy() { calls.push("destroy"); } };
  const exports = {};
  const createElement = () => {
    const node = { remove() { const i = children.indexOf(node); if (i >= 0) children.splice(i, 1); } };
    return node;
  };
  vm.runInNewContext(outputText, {
    exports, URLSearchParams,
    document: { createElement },
    window: { location: { origin: "http://localhost:3000" }, setTimeout(fn) { const id = timers.size + 1; timers.set(id, fn); return id; }, clearTimeout(id) { timers.delete(id); } },
  });
  const api = { Player: class {
    constructor(_host, options) { events = options.events; return target; }
  } };
  const controller = exports.createYouTubePlayback({ appendChild(node) { children.push(node); } }, api, {
    videoId: "C0bP9Sk3uUw", title: "KBO highlight", preview,
    onStatus(status, code) { statuses.push([status, code]); },
  });
  const ready = () => {
    // Real YT.Player has no playback methods until ready. This reproduces the bug.
    target.mute = () => calls.push("mute");
    target.playVideo = () => calls.push("play");
    target.pauseVideo = () => calls.push("pause");
    events.onReady({ target });
  };
  return { controller, children, calls, statuses, timers, ready, state: data => events.onStateChange({ target, data }), error: data => events.onError({ target, data }), blocked: () => events.onAutoplayBlocked({ target }) };
}

test("leaving before ready does not call missing methods or start a late preview", () => {
  const h = harness();
  h.controller.setActive(true);
  h.controller.setActive(false);
  assert.deepEqual(h.calls, []);
  h.ready();
  assert.deepEqual(h.calls, ["pause"]);
  assert.equal(h.timers.size, 0);
});

test("hover plays muted only after ready and playback is reported only after acknowledgement", () => {
  const h = harness();
  h.controller.setActive(true);
  h.ready();
  assert.deepEqual(h.calls, ["mute", "play"]);
  assert.equal(h.statuses.at(-1)[0], "ready");
  h.state(1);
  assert.equal(h.statuses.at(-1)[0], "playing");
  h.controller.setActive(false);
  h.state(1);
  assert.equal(h.calls.at(-1), "pause");
});

test("unmount before ready cleans iframe and ignores late callbacks", () => {
  const h = harness();
  h.controller.setActive(true);
  h.controller.destroy();
  h.ready();
  h.state(1);
  h.error(150);
  assert.deepEqual(h.calls, ["destroy"]);
  assert.deepEqual(h.statuses, []);
  assert.equal(h.children.length, 0);
  assert.equal(h.timers.size, 0);
  const remount = harness();
  remount.controller.setActive(true);
  remount.ready();
  assert.equal(remount.calls.at(-1), "play");
});

test("board supports autoplay blocking, retry by user action, and embed errors", () => {
  const h = harness(false);
  h.controller.setActive(true);
  h.ready();
  h.blocked();
  assert.equal(h.statuses.at(-1)[0], "blocked");
  h.controller.play();
  h.state(1);
  assert.equal(h.statuses.at(-1)[0], "playing");
  h.error(150);
  assert.deepEqual(h.statuses.at(-1), ["error", 150]);
  assert.match(h.children[0].src, /origin=http%3A%2F%2Flocalhost%3A3000/);
  assert.equal(h.children[0].referrerPolicy, "strict-origin-when-cross-origin");
});

test("an unresponsive embed produces an error instead of an endless blank player", () => {
  const h = harness(false);
  for (const timeout of h.timers.values()) timeout();
  assert.equal(h.statuses.at(-1)[0], "error");
});
