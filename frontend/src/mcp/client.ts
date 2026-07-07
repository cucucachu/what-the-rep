import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import type { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import type { CallToolResult, ReadResourceResult } from "@modelcontextprotocol/sdk/types.js";

import { DEFAULT_MCP_URL, getMcpUrl } from "./config.js";
import type {
  McpConnectionStatus,
  McpResourceContent,
  McpToolInfo,
} from "./types.js";
import { MCP_APP_MIME_TYPE } from "./types.js";

const CLIENT_NAME = "what-the-rep-frontend";
const CLIENT_VERSION = "0.0.0";

export class McpClientError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "McpClientError";
  }
}

export type McpClientDependencies = {
  createSdkClient?: () => Client;
  createTransport?: (url: URL) => Transport;
};

export function parseStructuredToolResult(result: CallToolResult): unknown {
  if (result.isError) {
    const message =
      result.content
        ?.filter((item) => item.type === "text")
        .map((item) => item.text)
        .join("\n")
        .trim() || "Tool call failed";
    throw new McpClientError(message);
  }

  if (result.structuredContent !== undefined) {
    return result.structuredContent;
  }

  const textBlock = result.content?.find((item) => item.type === "text");
  if (textBlock?.type === "text") {
    try {
      return JSON.parse(textBlock.text) as unknown;
    } catch {
      return { text: textBlock.text };
    }
  }

  return result.content ?? null;
}

function parseResourceContent(
  uri: string,
  result: ReadResourceResult,
): McpResourceContent {
  if (!result.contents || result.contents.length !== 1) {
    throw new McpClientError(
      `Expected 1 resource content for ${uri}, got ${result.contents?.length ?? 0}`,
    );
  }

  const content = result.contents[0];
  if (!("text" in content) || typeof content.text !== "string") {
    throw new McpClientError(`Resource ${uri} has no HTML text content`);
  }

  return {
    uri: content.uri ?? uri,
    mimeType: content.mimeType ?? MCP_APP_MIME_TYPE,
    text: content.text,
  };
}

export class WhatTheRepMcpClient {
  private client: Client | null = null;
  private transport: Transport | null = null;
  private status: McpConnectionStatus = "idle";
  private readonly url: string;
  private readonly deps: Required<McpClientDependencies>;

  constructor(url?: string, deps: McpClientDependencies = {}) {
    this.url = url ?? getMcpUrl();
    this.deps = {
      createSdkClient:
        deps.createSdkClient ??
        (() =>
          new Client({
            name: CLIENT_NAME,
            version: CLIENT_VERSION,
          })),
      createTransport:
        deps.createTransport ??
        ((target) => new StreamableHTTPClientTransport(target)),
    };
  }

  getConnectionStatus(): McpConnectionStatus {
    return this.status;
  }

  getUrl(): string {
    return this.url;
  }

  isConnected(): boolean {
    return this.status === "connected" && this.client !== null;
  }

  async connect(): Promise<void> {
    if (this.isConnected()) {
      return;
    }

    this.status = "connecting";

    try {
      const client = this.deps.createSdkClient();
      const transport = this.deps.createTransport(new URL(this.url));
      await client.connect(transport);

      this.client = client;
      this.transport = transport;
      this.status = "connected";
    } catch (error) {
      this.client = null;
      this.transport = null;
      this.status = "error";
      throw new McpClientError(
        error instanceof Error ? error.message : "Failed to connect to MCP server",
        { cause: error },
      );
    }
  }

  async disconnect(): Promise<void> {
    if (this.transport && "close" in this.transport) {
      await this.transport.close();
    }

    this.client = null;
    this.transport = null;
    this.status = "idle";
  }

  async listTools(): Promise<McpToolInfo[]> {
    const client = this.requireConnectedClient();
    const result = await client.listTools();
    return result.tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
      meta: tool._meta as McpToolInfo["meta"],
    }));
  }

  async callToolRaw(
    name: string,
    args: Record<string, unknown> = {},
  ): Promise<CallToolResult> {
    const client = this.requireConnectedClient();
    return (await client.callTool({
      name,
      arguments: args,
    })) as CallToolResult;
  }

  async readResource(uri: string): Promise<McpResourceContent> {
    const client = this.requireConnectedClient();
    const result = (await client.readResource({ uri })) as ReadResourceResult;
    return parseResourceContent(uri, result);
  }

  async callTool(
    name: string,
    args: Record<string, unknown> = {},
  ): Promise<unknown> {
    const result = await this.callToolRaw(name, args);
    return parseStructuredToolResult(result);
  }

  private requireConnectedClient(): Client {
    if (!this.client || this.status !== "connected") {
      throw new McpClientError("MCP client is not connected");
    }
    return this.client;
  }
}

export { DEFAULT_MCP_URL, getMcpUrl };
