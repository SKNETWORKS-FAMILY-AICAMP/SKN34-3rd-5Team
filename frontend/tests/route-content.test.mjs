import assert from "node:assert/strict";
import { after, test } from "node:test";
import { createRequire } from "node:module";
import { mkdtempSync, readFileSync, rmdirSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

// Exercise the actual pure module without starting Next or loading environment
// files. The scratch directory contains only this compiled module.
const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const scratch = mkdtempSync(join(tmpdir(), "kbo-route-content-test-"));
const compiledFile = join(scratch, "route-content.cjs");
after(() => { unlinkSync(compiledFile); rmdirSync(scratch); });
const source = readFileSync(join(frontend, "lib", "route-content.ts"), "utf8");
const { outputText } = ts.transpileModule(source, {
  fileName: "route-content.ts",
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
});
writeFileSync(compiledFile, outputText);
const requireTestModule = createRequire(join(scratch, "entry.cjs"));
const { routeContentToText, plainTextToHtml, safeRouteLink } = requireTestModule("./route-content.cjs");

test("legacy plain text preserves literal markup, entities, spacing and line breaks", () => {
  const content = '  <b>잠실</b> &amp; 친구\n\n<script>이것도 입력한 글이에요.</script>  ';
  assert.equal(routeContentToText(content), content);
  assert.equal(routeContentToText(content, undefined), content);
});

test("explicit editor HTML becomes readable paragraphs, lists and line breaks", () => {
  const content = '<h2>직관 코스</h2><p>먼저 <strong>식사</strong><br>그다음 입장</p><ul><li>잠실야구장</li><li>석촌호수</li></ul>';
  assert.equal(routeContentToText(content, "html"), "직관 코스\n\n먼저 식사\n그다음 입장\n\n잠실야구장\n석촌호수");
});

test("editor plain text excludes embedded executable and hidden element contents", () => {
  const content = '<p>방문 안내</p><script>alert("script payload")</script><STYLE>.hidden {display:none}</STYLE><iframe>frame payload</iframe><object>object payload</object><p>경기 관람</p>';
  const result = routeContentToText(content, "html");
  assert.equal(result, "방문 안내\n\n경기 관람");
  assert.doesNotMatch(result, /payload|alert|display|<\/?/);
});

test("editor entity decoding preserves quoted text without decoding twice", () => {
  assert.equal(routeContentToText('<p>&quot;잠실&quot;&nbsp;&amp;&nbsp;&apos;친구&#39; &lt;코스&gt; &#x27;야구&#x27;</p>', "html"), '"잠실" & \'친구\' <코스> \'야구\'');
  assert.equal(routeContentToText("<p>&amp;lt;script&amp;gt;</p>", "html"), "&lt;script&gt;");
});

test("blank plain text produces no editor markup", () => {
  assert.equal(plainTextToHtml(""), "");
  assert.equal(plainTextToHtml(" \n\t "), "");
});

test("plain text migration escapes HTML and preserves paragraph structure", () => {
  const text = '<img src=x onerror="alert(1)"> & 친구\n경기 관람\n\n다음 코스';
  const html = plainTextToHtml(text);
  assert.equal(html, '<p>&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; 친구<br>경기 관람</p><p>다음 코스</p>');
  assert.doesNotMatch(html, /<img\b|<script\b/);
  assert.equal(routeContentToText(html, "html"), text);
});

test("legacy literal tags and entity-looking text survive an editor conversion", () => {
  const text = '<script>글에 적은 예시</script> &lt;태그&gt; & "따옴표"\n두 번째 줄';
  assert.equal(routeContentToText(plainTextToHtml(text), "html"), text);
});

for (const [name, value] of [
  ["javascript scheme", "javascript:alert(1)"],
  ["mixed-case javascript scheme", "JaVaScRiPt:alert(1)"],
  ["control-character-obfuscated javascript scheme", "java\nscript:alert(1)"],
  ["HTML data URL", "data:text/html,<script>alert(1)</script>"],
  ["file URL", "file:///C:/Users/example/private.txt"],
  ["URL containing username", "https://user@example.test/path"],
  ["URL containing username and password", "https://user:secret@example.test/path"],
  ["encoded credential URL", "https://%75ser@example.test/path"],
  ["relative URL", "/routes/example"],
  ["protocol-relative URL", "//example.test/path"],
  ["malformed URL", "this is not a URL"],
  ["empty value", ""],
  ["missing value", null],
]) {
  test(`route links reject ${name}`, () => assert.equal(safeRouteLink(value), undefined));
}

test("route links allow HTTPS and preserve destination query and fragment", () => {
  assert.equal(safeRouteLink("https://map.kakao.com/?q=Jamsil#map"), "https://map.kakao.com/?q=Jamsil#map");
});

test("route links allow ordinary HTTP and mailto destinations", () => {
  assert.equal(safeRouteLink("http://example.test/guide"), "http://example.test/guide");
  assert.equal(safeRouteLink("mailto:route@example.test"), "mailto:route@example.test");
});
