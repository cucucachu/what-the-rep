import { spawn, type ChildProcess } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { loadFixtureManifest, MCP_BASE_URL, postMcp } from "./fixtures.js";
import { waitForWidgetReady } from "./helpers/widget-frame.js";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const backendDir = path.join(repoRoot, "backend");
const rateLimitPort = 8001;
const rateLimitUrl = `http://127.0.0.1:${rateLimitPort}/mcp`;

let rateLimitServer: ChildProcess | null = null;

function waitForPort(host: string, port: number, maxAttempts = 40) {
  return new Promise<void>((resolve, reject) => {
    let attempts = 0;
    const tryConnect = () => {
      attempts += 1;
      const socket = net.connect({ host, port }, () => {
        socket.end();
        resolve();
      });
      socket.on("error", () => {
        socket.destroy();
        if (attempts >= maxAttempts) {
          reject(new Error(`Port ${host}:${port} not ready`));
          return;
        }
        setTimeout(tryConnect, 250);
      });
    };
    tryConnect();
  });
}

async function startRateLimitBackend() {
  rateLimitServer = spawn("uv", ["run", "python", "-m", "mcp_server"], {
    cwd: backendDir,
    env: {
      ...process.env,
      MONGODB_URI: process.env.MONGODB_URI ?? "mongodb://127.0.0.1:27017",
      MONGODB_DB_NAME: process.env.MONGODB_DB_NAME ?? "what_the_rep_e2e",
      MCP_HOST: "127.0.0.1",
      MCP_PORT: String(rateLimitPort),
      RATE_LIMIT_READ_PER_MIN: "2",
      RATE_LIMIT_READ_PER_DAY: "10000",
      MCP_CORS_ALLOW_ORIGINS: "http://127.0.0.1:4173",
    },
    stdio: "ignore",
    shell: process.platform === "win32",
  });

  await waitForPort("127.0.0.1", rateLimitPort);
  await new Promise((resolve) => setTimeout(resolve, 500));
}

test.describe("T20 MVP acceptance suite", () => {
  test.describe.configure({ mode: "serial" });

  test("1. ingestion pipeline seeded Novato + Marin fixtures into clean DB", async () => {
    const manifest = loadFixtureManifest();

    expect(manifest.jurisdictionCount).toBeGreaterThanOrEqual(4);
    expect(manifest.meetingCount).toBe(2);
    expect(manifest.actionCount).toBeGreaterThanOrEqual(7);
    expect(manifest.novatoMeetingExternalId).toBe("1980");
    expect(manifest.novatoMeetingDatePrefix).toBe("2024-01-23");
    expect(manifest.expectedVoteTally).toEqual({ ayes: 4, noes: 1 });
    expect(manifest.nonUnanimousActionExternalIdPattern).toBe("2024-011");
    expect(manifest.dissentingOfficialName).toMatch(/Eklund/i);
    expect(manifest.novatoOfficeholderNames.length).toBeGreaterThanOrEqual(4);
  });

  test("2. MCP server and frontend are running against seeded database", async ({
    page,
    request,
  }) => {
    const ping = await postMcp(request, MCP_BASE_URL, {});
    expect(ping.status()).not.toBe(429);

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /what the rep/i }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: /where are you/i })).toBeVisible();
  });

  test("3. home location flow renders home-summary widget with Novato data", async ({
    page,
  }) => {
    const manifest = loadFixtureManifest();

    await page.goto("/");
    await page.getByRole("button", { name: /try novato/i }).click();

    const frame = await waitForWidgetReady(page, "get_home_summary");
    await expect(
      frame.getByRole("heading", { name: "Government Activity Summary" }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(frame.getByRole("heading", { name: "City of Novato" })).toBeVisible();

    for (const name of manifest.novatoOfficeholderNames.slice(0, 3)) {
      await expect(frame.getByText(name, { exact: false }).first()).toBeVisible();
    }

    await expect(frame.getByText(manifest.novatoMeetingDatePrefix).first()).toBeVisible();
    await expect(frame.getByText(/General Plan Land Use Map/i).first()).toBeVisible();
  });

  test("4. meeting page shows agenda and actions from ingested fixtures", async ({
    page,
  }) => {
    const manifest = loadFixtureManifest();

    await page.goto(`/meeting/${manifest.novatoMeetingId}`);

    await expect(page.getByRole("heading", { level: 2 })).toContainText("2024");
    await expect(page.getByText(manifest.governingBodyName)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Agenda items", exact: true })).toBeVisible();

    if (manifest.sampleAgendaItemTitle) {
      await expect(page.getByText(manifest.sampleAgendaItemTitle)).toBeVisible();
    }

    await expect(
      page.getByRole("link", {
        name: /finding the proposed General Plan Land Use Map/i,
      }).first(),
    ).toBeVisible();
  });

  test("5. non-unanimous action page vote-tally widget shows 4-1 passed", async ({
    page,
    request,
  }) => {
    const manifest = loadFixtureManifest();

    const actionData = await postMcp(request, MCP_BASE_URL, {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: "get_action",
        arguments: { action_id: manifest.nonUnanimousActionId },
      },
    });
    expect(actionData.status()).toBeLessThan(500);

    await page.goto(`/action/${manifest.nonUnanimousActionId}`);

    await expect(page.getByText(`Outcome: ${manifest.expectedOutcome}`)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Vote tally" })).toBeVisible();

    const frame = await waitForWidgetReady(page, "get_action");
    await expect(frame.getByText(manifest.expectedOutcome, { exact: false })).toBeVisible({
      timeout: 30_000,
    });
    await expect(frame.locator(".tally-item.aye .count")).toHaveText(
      String(manifest.expectedVoteTally.ayes),
    );
    await expect(frame.locator(".tally-item.no .count")).toHaveText(
      String(manifest.expectedVoteTally.noes),
    );
    await expect(frame.getByRole("heading", { name: /Noes/i })).toBeVisible();
    await expect(
      frame.getByText(manifest.dissentingOfficialName ?? "Eklund", { exact: false }),
    ).toBeVisible();
  });

  test("6. official page voting-history widget shows bio, tenure, and votes", async ({
    page,
  }) => {
    const manifest = loadFixtureManifest();

    await page.goto(`/official/${manifest.dissentingOfficialId}`);

    await expect(
      page.getByRole("heading", {
        name: manifest.dissentingOfficialName ?? "Pat Eklund",
      }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tenure history" })).toBeVisible();
    await expect(page.getByText(/City of Novato|Novato/i)).toBeVisible();

    const frame = await waitForWidgetReady(page, "get_official");
    await expect(
      frame.getByRole("heading", {
        name: manifest.dissentingOfficialName ?? "Pat Eklund",
      }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(frame.getByText(/2024-011|General Plan/i).first()).toBeVisible();
    await expect(frame.locator(".vote-badge.no").first()).toBeVisible();
  });

  test("7. rapid-fire requests past limit return HTTP 429 without affecting UI backend", async ({
    request,
  }) => {
    await startRateLimitBackend();

    try {
      const first = await postMcp(request, rateLimitUrl, {});
      const second = await postMcp(request, rateLimitUrl, {});
      const third = await postMcp(request, rateLimitUrl, {});

      expect(first.status()).not.toBe(429);
      expect(second.status()).not.toBe(429);
      expect(third.status()).toBe(429);

      const body = (await third.json()) as { detail?: string };
      expect(body.detail).toBe("Rate limit exceeded");
      expect(third.headers()["retry-after"]).toBeTruthy();

      const mainBackend = await postMcp(request, MCP_BASE_URL, {});
      expect(mainBackend.status()).not.toBe(429);
    } finally {
      if (rateLimitServer) {
        rateLimitServer.kill();
        rateLimitServer = null;
      }
    }
  });
});
