import { defineConfig, devices } from "@playwright/test";

const frontendPort = 4173;
const backendPort = 8000;

// Option B: Playwright webServer boots backend (uv) + frontend (vite preview) with a
// global-setup that seeds Mongo and builds the app. Faster in CI than full docker compose
// image builds; keeps the existing unit-test jobs unchanged.
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
      command: "node e2e/scripts/start-backend.mjs",
      stdout: /MCP_BACKEND_READY/,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        MCP_PORT: String(backendPort),
        MCP_CORS_ALLOW_ORIGINS: `http://127.0.0.1:${frontendPort},http://localhost:${frontendPort}`,
        MONGODB_URI: process.env.MONGODB_URI ?? "mongodb://127.0.0.1:27017",
        MONGODB_DB_NAME: process.env.MONGODB_DB_NAME ?? "what_the_rep_e2e",
      },
    },
    {
      command: `npm run preview -- --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
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
