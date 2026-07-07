import type { Tool } from "@modelcontextprotocol/sdk/types.js";

export type McpToolMeta = Record<string, unknown>;

export type McpToolInfo = {
  name: string;
  description?: string;
  inputSchema?: Tool["inputSchema"];
  /** FastMCP tool `_meta`, including `ui.resourceUri` for MCP Apps widgets. */
  meta?: McpToolMeta;
};

export type McpConnectionStatus = "idle" | "connecting" | "connected" | "error";

/** MIME type for MCP Apps HTML resources (`resources/read`). */
export const MCP_APP_MIME_TYPE = "text/html;profile=mcp-app";

export type McpResourceContent = {
  uri: string;
  mimeType: string;
  text: string;
};

/** Shape expected by MCP-UI hosts (`UIResource` / AppRenderer resource content). */
export type McpUiResource = {
  type: "resource";
  resource: McpResourceContent;
};
