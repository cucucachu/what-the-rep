import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type E2EFixtureManifest = {
  novatoMeetingId: string;
  novatoMeetingExternalId: string;
  novatoMeetingDatePrefix: string;
  governingBodyName: string;
  sampleAgendaItemTitle: string | null;
  nonUnanimousActionId: string;
  nonUnanimousActionExternalIdPattern: string;
  nonUnanimousActionDescription: string | null;
  expectedVoteTally: { ayes: number; noes: number };
  expectedOutcome: string;
  dissentingOfficialId: string;
  dissentingOfficialSlug: string | null;
  dissentingOfficialName: string | null;
  dissentingVote: string;
  novatoOfficeholderNames: string[];
  jurisdictionCount: number;
  meetingCount: number;
  actionCount: number;
};

const manifestPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  ".runtime",
  "fixture-manifest.json",
);

let cachedManifest: E2EFixtureManifest | null = null;

export function loadFixtureManifest(): E2EFixtureManifest {
  if (cachedManifest) {
    return cachedManifest;
  }
  if (!fs.existsSync(manifestPath)) {
    throw new Error(
      `Missing E2E fixture manifest at ${manifestPath}. Run global-setup first.`,
    );
  }
  cachedManifest = JSON.parse(fs.readFileSync(manifestPath, "utf8")) as E2EFixtureManifest;
  return cachedManifest;
}

export const MCP_BASE_URL =
  process.env.MCP_BASE_URL ?? "http://127.0.0.1:8000/mcp";

export async function postMcp(
  request: { post: (url: string, options?: object) => Promise<{ status: () => number; json: () => Promise<unknown>; headers: () => Record<string, string> }> },
  url: string,
  body: unknown = {},
  headers: Record<string, string> = {},
) {
  return request.post(url.replace(/\/$/, ""), {
    data: body,
    headers: {
      "content-type": "application/json",
      ...headers,
    },
  });
}
