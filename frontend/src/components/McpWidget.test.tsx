import { render, screen, waitFor } from "@testing-library/react";
import type { CallToolRequest, CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MCP_APP_MIME_TYPE } from "../mcp/types.js";
import { toMcpUiResource } from "../mcp/ui-resource.js";
import { WhatTheRepMcpClient } from "../mcp/client.js";
import { McpWidget } from "./McpWidget.js";

const mockAppRenderer = vi.fn(
  (props: {
    html?: string;
    toolResourceUri?: string;
    toolInput?: Record<string, unknown>;
    toolResult?: CallToolResult;
    onCallTool?: (
      params: CallToolRequest["params"],
      extra: unknown,
    ) => Promise<CallToolResult>;
  }) => (
    <div
      data-testid="app-renderer"
      data-uri={props.toolResourceUri}
      data-html={props.html}
    />
  ),
);

vi.mock("@mcp-ui/client", () => ({
  AppRenderer: (props: unknown) => mockAppRenderer(props as never),
}));

const DEMO_URI = "ui://what-the-rep/demo-widget";
const DEMO_HTML = "<html><body><h1>Demo widget</h1></body></html>";

function createMockClient(): WhatTheRepMcpClient {
  const toolResult: CallToolResult = {
    structuredContent: { status: "ok" },
    content: [{ type: "text", text: '{"status":"ok"}' }],
  };

  return {
    callToolRaw: vi.fn().mockResolvedValue(toolResult),
    callTool: vi.fn().mockResolvedValue({ status: "ok" }),
    listTools: vi.fn().mockResolvedValue([
      {
        name: "demo_widget",
        description: "Demo widget tool",
        meta: {
          ui: { resourceUri: DEMO_URI },
        },
      },
    ]),
    readResource: vi.fn().mockResolvedValue({
      uri: DEMO_URI,
      mimeType: MCP_APP_MIME_TYPE,
      text: DEMO_HTML,
    }),
  } as unknown as WhatTheRepMcpClient;
}

describe("McpWidget", () => {
  beforeEach(() => {
    mockAppRenderer.mockClear();
  });

  it("calls the tool, reads the ui:// resource, and renders via AppRenderer", async () => {
    const client = createMockClient();

    render(
      <McpWidget
        client={client}
        toolName="demo_widget"
        toolArgs={{ slug: "novato-ca" }}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(/loading widget/i);

    await waitFor(() => {
      expect(screen.getByTestId("app-renderer")).toBeInTheDocument();
    });

    expect(client.callToolRaw).toHaveBeenCalledWith("demo_widget", {
      slug: "novato-ca",
    });
    expect(client.listTools).toHaveBeenCalled();
    expect(client.readResource).toHaveBeenCalledWith(DEMO_URI);

    const rendererProps = mockAppRenderer.mock.calls.at(-1)?.[0];
    expect(rendererProps?.toolResourceUri).toBe(DEMO_URI);
    expect(rendererProps?.html).toBe(DEMO_HTML);
    expect(rendererProps?.toolInput).toEqual({ slug: "novato-ca" });

    const uiResource = toMcpUiResource({
      uri: DEMO_URI,
      mimeType: MCP_APP_MIME_TYPE,
      text: DEMO_HTML,
    });
    expect(uiResource).toEqual({
      type: "resource",
      resource: {
        uri: DEMO_URI,
        mimeType: MCP_APP_MIME_TYPE,
        text: DEMO_HTML,
      },
    });
    expect(rendererProps?.html).toBe(uiResource.resource.text);
  });

  it("forwards widget-initiated tool calls through the host handler", async () => {
    const client = createMockClient();
    const followUpResult: CallToolResult = {
      structuredContent: { voted: true },
      content: [{ type: "text", text: '{"voted":true}' }],
    };
    vi.mocked(client.callToolRaw).mockResolvedValueOnce({
      structuredContent: { status: "ok" },
      content: [{ type: "text", text: '{"status":"ok"}' }],
    });
    vi.mocked(client.callToolRaw).mockResolvedValueOnce(followUpResult);

    render(<McpWidget client={client} toolName="demo_widget" />);

    await waitFor(() => {
      expect(screen.getByTestId("app-renderer")).toBeInTheDocument();
    });

    const rendererProps = mockAppRenderer.mock.calls.at(-1)?.[0];
    expect(rendererProps?.onCallTool).toBeTypeOf("function");

    const result = await rendererProps?.onCallTool?.(
      { name: "cast_vote", arguments: { action_id: "abc" } },
      {},
    );

    expect(client.callToolRaw).toHaveBeenLastCalledWith("cast_vote", {
      action_id: "abc",
    });
    expect(result).toEqual(followUpResult);
  });
});
