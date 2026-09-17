import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../lib/browser-share.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;

function load({ secure = false, share, clipboard, copied = false } = {}) {
  class HTMLElement { focus() {} }
  const field = new HTMLElement();
  Object.assign(field, { style: {}, setAttribute() {}, select() {}, setSelectionRange() {}, remove() {}, value: "", readOnly: false });
  const context = {
    exports: {}, HTMLElement, Error, DOMException,
    window: { isSecureContext: secure },
    navigator: { share, clipboard },
    document: { activeElement: new HTMLElement(), createElement: () => field, body: { appendChild() {} }, execCommand: () => copied },
  };
  vm.runInNewContext(code, context);
  return context.exports.shareOrCopy;
}

test("secure browsers prefer native share", async () => {
  const shareOrCopy = load({ secure: true, share: async () => {} });
  assert.equal(await shareOrCopy({ title: "코스" }, "코스"), "shared");
});

test("cancelled native share is not reported as a copy failure", async () => {
  const shareOrCopy = load({ secure: true, share: async () => { throw new DOMException("cancel", "AbortError"); } });
  assert.equal(await shareOrCopy({ title: "코스" }, "코스"), "cancelled");
});

test("HTTP uses selection copy and reports manual fallback honestly", async () => {
  assert.equal(await load({ copied: true })({}, "코스"), "copied");
  assert.equal(await load({ copied: false })({}, "코스"), "manual");
});
