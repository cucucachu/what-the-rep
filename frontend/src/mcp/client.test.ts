import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import type { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  McpClientError,
  WhatTheRepMcpClient,
  parseStructuredToolResult,
} from "./client.js";

function createMockSdkClient(handlers: {
  connect?: Client["connect"];
  listTools?: Client["listTools"];
  callTool?: Client["callTool"];
  readResource?: Client["readResource"];
}): Client {
  return {
    connect: handlers.connect ?? vi.fn().mockResolvedValue(undefined),
    listTools:
      handlers.listTools ??
      vi.fn().mockResolvedValue({
        tools: [{ name: "ping", description: "Health check" }],
      }),
    callTool:
      handlers.callTool ??
      vi.fn().mockResolvedValue({
        structuredContent: { status: "ok" },
      }),
    readResource:
      handlers.readResource ??
      vi.fn().mockResolvedValue({
        contents: [
          {
            uri: "ui://what-the-rep/demo",
            mimeType: "text/html;profile=mcp-app",
            text: "<html><body>demo</body></html>",
          },
        ],
      }),
  } as unknown as Client;
}

function createMockTransport(): Transport {
  return {
    close: vi.fn().mockResolvedValue(undefined),
  } as unknown as Transport;
}

describe("parseStructuredToolResult", () => {
  it("returns structuredContent when present", () => {
    const result = parseStructuredToolResult({
      content: [],
      structuredContent: { jurisdictions: [{ slug: "novato-ca" }] },
    } as CallToolResult);

    expect(result).toEqual({ jurisdictions: [{ slug: "novato-ca" }] });
  });

  it("throws McpClientError when isError is true", () => {
    expect(() =>
      parseStructuredToolResult({
        content: [{ type: "text", text: "Rate limit exceeded" }],
        isError: true,
      } as CallToolResult),
    ).toThrow(new McpClientError("Rate limit exceeded"));
  });

  it("parses JSON from text content when structuredContent is absent", () => {
    const result = parseStructuredToolResult({
      content: [{ type: "text", text: '{"status":"ok"}' }],
    } as CallToolResult);

    expect(result).toEqual({ status: "ok" });
  });
});

describe("WhatTheRepMcpClient", () => {
  let mockClient: Client;
  let mockTransport: Transport;

  beforeEach(() => {
    mockTransport = createMockTransport();
    mockClient = createMockSdkClient({});
  });

  it("connects via injected transport and SDK client", async () => {
    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await client.connect();

    expect(mockClient.connect).toHaveBeenCalledWith(mockTransport);
    expect(client.isConnected()).toBe(true);
    expect(client.getConnectionStatus()).toBe("connected");
  });

  it("surfaces connection errors as McpClientError", async () => {
    mockClient = createMockSdkClient({
      connect: vi.fn().mockRejectedValue(new Error("Network down")),
    });

    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await expect(client.connect()).rejects.toThrow(McpClientError);
    await expect(client.connect()).rejects.toThrow("Network down");
    expect(client.getConnectionStatus()).toBe("error");
  });

  it("lists tools after connecting", async () => {
    mockClient = createMockSdkClient({
      listTools: vi.fn().mockResolvedValue({
        tools: [
          {
            name: "list_jurisdictions",
            description: "List jurisdictions",
            _meta: { ui: { resourceUri: "ui://what-the-rep/home-summary" } },
          },
          { name: "ping", description: "Health check" },
        ],
      }),
    });

    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await client.connect();
    const tools = await client.listTools();

    expect(tools).toEqual([
      {
        name: "list_jurisdictions",
        description: "List jurisdictions",
        meta: { ui: { resourceUri: "ui://what-the-rep/home-summary" } },
      },
      { name: "ping", description: "Health check", meta: undefined },
    ]);
  });

  it("callTool returns parsed structured content", async () => {
    mockClient = createMockSdkClient({
      callTool: vi.fn().mockResolvedValue({
        structuredContent: {
          jurisdictions: [{ slug: "novato-ca", name: "City of Novato" }],
        },
      }),
    });

    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await client.connect();
    const result = await client.callTool("list_jurisdictions");

    expect(mockClient.callTool).toHaveBeenCalledWith({
      name: "list_jurisdictions",
      arguments: {},
    });
    expect(result).toEqual({
      jurisdictions: [{ slug: "novato-ca", name: "City of Novato" }],
    });
  });

  it("callTool propagates tool errors", async () => {
    mockClient = createMockSdkClient({
      callTool: vi.fn().mockResolvedValue({
        isError: true,
        content: [{ type: "text", text: "Unknown tool" }],
      }),
    });

    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await client.connect();
    await expect(client.callTool("missing_tool")).rejects.toThrow(
      new McpClientError("Unknown tool"),
    );
  });

  it("requires a connection before calling tools", async () => {
    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await expect(client.listTools()).rejects.toThrow(
      new McpClientError("MCP client is not connected"),
    );
  });

  it("readResource returns HTML content from resources/read", async () => {
    const client = new WhatTheRepMcpClient("http://127.0.0.1:8000/mcp/", {
      createSdkClient: () => mockClient,
      createTransport: () => mockTransport,
    });

    await client.connect();
    const resource = await client.readResource("ui://what-the-rep/demo");

    expect(mockClient.readResource).toHaveBeenCalledWith({
      uri: "ui://what-the-rep/demo",
    });
    expect(resource).toEqual({
      uri: "ui://what-the-rep/demo",
      mimeType: "text/html;profile=mcp-app",
      text: "<html><body>demo</body></html>",
    });
  });
});
