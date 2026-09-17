import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const mode = process.argv[2] ?? "generate";
if (!new Set(["generate", "check"]).has(mode)) throw new Error("usage: contracts.mjs generate|check");

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(frontend, "..");
const targets = [join(root, "contracts", "openapi.yaml"), join(frontend, "lib", "api", "schema.d.ts")];
const work = mkdtempSync(join(tmpdir(), "kbo-contracts-"));
const generated = [join(work, "openapi.yaml"), join(work, "schema.d.ts")];

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit", ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} exited with ${result.status}`);
}

try {
  const spectacularArgs = [join(root, "backend", "manage.py"), "spectacular", "--file", generated[0], "--validate"];
  if (mode === "check") spectacularArgs.push("--fail-on-warn");
  run(process.env.CONTRACT_PYTHON || "python3", spectacularArgs, {
    env: {
      PATH: process.env.PATH,
      PYTHON_DOTENV_DISABLED: "1",
      DJANGO_ALLOWED_HOSTS: "localhost",
      DB_NAME: "schema",
      DB_USER: "schema",
      DB_PASSWORD: "schema",
      DB_HOST: "localhost",
      BASEBALL_DB_USER: "schema",
      BASEBALL_DB_PASSWORD: "schema",
      EMAIL_BACKEND: "django.core.mail.backends.locmem.EmailBackend",
      CHAT_CHECKPOINT_SIGNING_KEY: "schema-only",
    },
  });
  run(join(frontend, "node_modules", ".bin", "openapi-typescript"), [generated[0], "--output", generated[1]]);

  if (mode === "check") {
    const stale = targets.filter((target, index) => !existsSync(target) || !readFileSync(target).equals(readFileSync(generated[index])));
    if (stale.length) throw new Error(`generated contracts are stale: ${stale.map(path => path.replace(`${root}/`, "")).join(", ")}`);
  } else {
    targets.forEach((target, index) => { mkdirSync(dirname(target), { recursive: true }); copyFileSync(generated[index], target); });
    console.log("generated contracts/openapi.yaml and frontend/lib/api/schema.d.ts");
  }
} finally {
  rmSync(work, { recursive: true, force: true });
}
