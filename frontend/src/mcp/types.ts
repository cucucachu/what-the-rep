import type { Tool } from "@modelcontextprotocol/sdk/types.js";

export type McpToolInfo = Pick<Tool, "name" | "description" | "inputSchema">;

export type McpConnectionStatus = "idle" | "connecting" | "connected" | "error";
