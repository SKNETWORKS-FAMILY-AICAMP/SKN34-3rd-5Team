import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";

const frontend = new URL("../", import.meta.url);
const source = readFileSync(new URL("lib/community-api.ts", frontend), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } });
const testModule = { exports: {} };
const require = name => name === "react"
  ? { useEffect() {}, useSyncExternalStore() {} }
  : { teamBoards: ["LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO"].map(code => ({ code })) };
new Function("module", "exports", "require", outputText)(testModule, testModule.exports, require);
const { fetchCommunityPosts } = testModule.exports;
const post = {
  id: "free-sample-1", sourceId: "free-sample-1", postNumber: "020001", board: "free", teamCode: "",
  author: "예시 작성자", title: "제목", content: "본문", category: "잡담", createdAt: null,
  views: 0, recommendations: 0, commentCount: 0, isSample: true,
};

test("community list is read from the public DB API", async () => {
  const result = await fetchCommunityPosts(async (url, init) => {
    assert.equal(url, "/api/community/posts/");
    assert.equal(init.cache, "no-store");
    assert.ok(init.signal instanceof AbortSignal);
    return Response.json([post]);
  });
  assert.deepEqual(result, [post]);
});

test("API and malformed payload failures stay failures without fixture fallback", async () => {
  await assert.rejects(fetchCommunityPosts(async () => new Response(null, { status: 503 })), /Community API 503/);
  await assert.rejects(fetchCommunityPosts(async () => Response.json([{ ...post, sourceId: "other" }])), /Invalid community response/);

  for (const file of [
    "components/community-board.tsx", "components/team-community-board.tsx", "components/home-team-boards.tsx",
  ]) {
    const caller = readFileSync(new URL(file, frontend), "utf8");
    assert.doesNotMatch(caller, /getFreeBoardPosts|getTeamBoardPosts|free-community-examples|team-community-examples/);
    assert.match(caller, /useCommunityPosts/);
    assert.match(caller, /다시 (시도|확인)/);
  }
});
