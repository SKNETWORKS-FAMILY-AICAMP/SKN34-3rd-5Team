import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const python = process.env.CONTRACT_PYTHON;

test("contract check rejects the current unresolved schema", { skip: !python }, () => {
  const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
  const result = spawnSync(process.execPath, [join(frontend, "scripts", "contracts.mjs"), "check"], {
    cwd: frontend,
    encoding: "utf8",
    env: { ...process.env, CONTRACT_PYTHON: python },
  });
  const output = `${result.stdout}${result.stderr}`;
  const unresolved = /(?:Warnings|Errors):\s+[1-9]\d*/.test(output);
  assert.equal(unresolved ? result.status !== 0 : result.status === 0, true, output);
});
