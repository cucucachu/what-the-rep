import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const manifestPath = path.join(__dirname, ".runtime", "fixture-manifest.json");

function run(command: string, args: string[], cwd: string, env: NodeJS.ProcessEnv) {
  const result = spawnSync(command, args, {
    cwd,
    env,
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with code ${result.status ?? "unknown"}`);
  }
}

export default async function globalSetup() {
  const mongoUri = process.env.MONGODB_URI ?? "mongodb://127.0.0.1:27017";
  const dbName = process.env.MONGODB_DB_NAME ?? "what_the_rep_e2e";

  const distIndex = path.join(__dirname, "..", "dist", "index.html");
  if (!fs.existsSync(distIndex)) {
    throw new Error(
      `Missing ${distIndex}. Playwright starts webServer before globalSetup, so ` +
        "run `npm run build` (with VITE_MCP_URL set) before `npm run test:e2e`.",
    );
  }

  const seedEnv = {
    ...process.env,
    MONGODB_URI: mongoUri,
    MONGODB_DB_NAME: dbName,
  };

  console.log("[e2e] Seeding test database via scripts/seed_all.py …");
  run(
    "uv",
    ["run", "python", path.join("..", "scripts", "seed_all.py")],
    path.join(repoRoot, "backend"),
    seedEnv,
  );

  console.log("[e2e] Generating fixture manifest …");
  fs.mkdirSync(path.dirname(manifestPath), { recursive: true });
  run(
    "uv",
    [
      "run",
      "python",
      path.join("..", "scripts", "generate_e2e_manifest.py"),
      manifestPath,
    ],
    path.join(repoRoot, "backend"),
    seedEnv,
  );

  if (!fs.existsSync(manifestPath)) {
    throw new Error(`Fixture manifest was not created at ${manifestPath}`);
  }
}
