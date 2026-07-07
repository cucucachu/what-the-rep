import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../../..");
const backendDir = path.join(repoRoot, "backend");
const host = process.env.MCP_HOST ?? "127.0.0.1";
const port = Number.parseInt(process.env.MCP_PORT ?? "8000", 10);

const env = {
  ...process.env,
  MONGODB_URI: process.env.MONGODB_URI ?? "mongodb://127.0.0.1:27017",
  MONGODB_DB_NAME: process.env.MONGODB_DB_NAME ?? "what_the_rep_e2e",
  MCP_HOST: host,
  MCP_PORT: String(port),
  MCP_CORS_ALLOW_ORIGINS:
    process.env.MCP_CORS_ALLOW_ORIGINS ??
    "http://127.0.0.1:4173,http://localhost:4173",
  RATE_LIMIT_READ_PER_MIN: process.env.RATE_LIMIT_READ_PER_MIN ?? "120",
  RATE_LIMIT_READ_PER_DAY: process.env.RATE_LIMIT_READ_PER_DAY ?? "10000",
};

function waitForPort(maxAttempts = 60) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const tryConnect = () => {
      attempts += 1;
      const socket = net.connect({ host, port }, () => {
        socket.end();
        resolve(undefined);
      });
      socket.on("error", () => {
        socket.destroy();
        if (attempts >= maxAttempts) {
          reject(new Error(`Backend did not listen on ${host}:${port}`));
          return;
        }
        setTimeout(tryConnect, 500);
      });
    };

    tryConnect();
  });
}

const child = spawn("uv", ["run", "python", "-m", "mcp_server"], {
  cwd: backendDir,
  env,
  stdio: "inherit",
  shell: process.platform === "win32",
});

child.on("error", (error) => {
  console.error(error);
  process.exit(1);
});

waitForPort()
  .then(() => {
    console.log("MCP_BACKEND_READY");
  })
  .catch((error) => {
    console.error(error);
    child.kill();
    process.exit(1);
  });

function shutdown() {
  child.kill();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
child.on("exit", (code) => process.exit(code ?? 0));
