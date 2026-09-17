import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const source = readFileSync(join(frontend, "components", "stadium-parking-map-dialog.tsx"), "utf8");

test("parking maps use their reliable original URL and unique dialog labels", () => {
  assert.match(source, /<Image[\s\S]*?unoptimized[\s\S]*?\/>/);
  assert.doesNotMatch(source, /\b(?:sizes|priority)=?/);
  assert.match(source, /const id = useId\(\)/);
  assert.match(source, /parking-map-title-\$\{parking\.stadiumCode\.toLowerCase\(\)\}-\$\{id\}/);
  assert.match(source, /parking-map-description-\$\{parking\.stadiumCode\.toLowerCase\(\)\}-\$\{id\}/);
});
