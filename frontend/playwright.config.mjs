import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.resolve(__dirname, "..", "backend");

const frontendPort = 4173;
const backendPort = 8000;

const mongoUri = process.env.MONGODB_URI ?? "mongodb://127.0.0.1:27017";
const mongoDbName = process.env.MONGODB_DB_NAME ?? "what_the_rep_e2e";
const corsOrigins = `http://127.0.0.1:${frontendPort},http://localhost:${frontendPort}`;

// Option B: Playwright webServer boots backend (uv) + frontend (vite preview) with a
// global-setup that seeds Mongo and builds the app. Readiness uses url polling on
// GET /healthz (200). Playwright only treats status codes 200-403 as ready, so
// /mcp (406 after redirect) cannot be used as the readiness URL.
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  timeout: 60_000,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "uv run python -m mcp_server",
      cwd: backendDir,
      url: `http://127.0.0.1:${backendPort}/healthz`,
      stdout: "pipe",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        MCP_HOST: "127.0.0.1",
        MCP_PORT: String(backendPort),
        MCP_CORS_ALLOW_ORIGINS: corsOrigins,
        MONGODB_URI: mongoUri,
        MONGODB_DB_NAME: mongoDbName,
        RATE_LIMIT_READ_PER_MIN: "120",
        RATE_LIMIT_READ_PER_DAY: "10000",
      },
    },
    {
      command: `npm run preview -- --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
      stdout: "pipe",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
