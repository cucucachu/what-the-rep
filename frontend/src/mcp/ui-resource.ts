import type { McpResourceContent, McpToolInfo, McpUiResource } from "./types.js";
import { MCP_APP_MIME_TYPE } from "./types.js";

export function getToolUiResourceUri(
  meta: McpToolInfo["meta"],
): string | null {
  if (!meta) {
    return null;
  }
  const ui = meta.ui;
  if (!ui || typeof ui !== "object") {
    return null;
  }
  const resourceUri = (ui as Record<string, unknown>).resourceUri;
  return typeof resourceUri === "string" ? resourceUri : null;
}

export function findToolUiResourceUri(
  tools: McpToolInfo[],
  toolName: string,
): string | null {
  const tool = tools.find((entry) => entry.name === toolName);
  return tool ? getToolUiResourceUri(tool.meta) : null;
}

export function toMcpUiResource(content: McpResourceContent): McpUiResource {
  return {
    type: "resource",
    resource: {
      uri: content.uri,
      mimeType: content.mimeType || MCP_APP_MIME_TYPE,
      text: content.text,
    },
  };
}

export function getSandboxProxyUrl(origin: string = window.location.origin): URL {
  return new URL("/sandbox_proxy.html", origin);
}
