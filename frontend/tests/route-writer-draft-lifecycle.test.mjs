import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const source = readFileSync(join(frontend, "components", "route-writer.tsx"), "utf8");

test("writer has a stable server hydration boundary before reading browser drafts", () => {
  assert.match(source, /useSyncExternalStore\(noClientChange, clientReady, serverReady\)/);
  assert.match(source, /if \(!hydrated\) return [\s\S]*?<WriterForm/);
});

test("public success switches the live form to canonical edit autosave without stopping its scheduler", () => {
  const success = source.slice(source.indexOf("const oldContext = draftContext.current"), source.indexOf("const showSavedCourse"));
  assert.match(success, /draftContext\.current = canonicalContext/);
  assert.match(success, /expectedRaw\.current = null/);
  assert.match(success, /savedRouteRef\.current = persisted/);
  assert.match(success, /searchParams\.set\("edit", persisted\.id\)/);
  assert.doesNotMatch(success, /autosaveRef\.current\?\.stop|publishedRef/);
});

test("review continuation does not depend on same-URL navigation remounting the writer", () => {
  const review = source.slice(source.indexOf('title: "코스 후기를 작성하시겠어요?"'), source.indexOf("} else if (!persisted.saveWarning)"));
  assert.doesNotMatch(review, /router\.(push|replace)/);
  assert.match(review, /setTab\("write"\)/);
});
