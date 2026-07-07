import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { McpConnectivityPanel } from "./McpConnectivityPanel.js";
import { WhatTheRepMcpClient } from "../mcp/client.js";

function createMockClient(
  behavior: "success" | "failure",
): WhatTheRepMcpClient {
  return {
    getUrl: () => "http://127.0.0.1:8000/mcp/",
    connect:
      behavior === "success"
        ? vi.fn().mockResolvedValue(undefined)
        : vi.fn().mockRejectedValue(new Error("Connection refused")),
    listTools:
      behavior === "success"
        ? vi.fn().mockResolvedValue([
            { name: "list_jurisdictions", description: "List jurisdictions" },
            { name: "ping", description: "Health check" },
          ])
        : vi.fn(),
    callTool:
      behavior === "success"
        ? vi.fn().mockResolvedValue({
            jurisdictions: [{ slug: "novato-ca", name: "City of Novato" }],
          })
        : vi.fn(),
    disconnect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(behavior === "success"),
    getConnectionStatus: vi.fn().mockReturnValue("connected"),
  } as unknown as WhatTheRepMcpClient;
}

describe("McpConnectivityPanel", () => {
  it("shows loading then tools and raw JSON on success", async () => {
    render(<McpConnectivityPanel client={createMockClient("success")} />);

    expect(screen.getByRole("status")).toHaveTextContent("Connecting…");
    expect(
      screen.getByText(/loading tools and sample result/i),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent("Connected");
    });

    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByText("list_jurisdictions").length).toBeGreaterThan(0);
    expect(screen.getByText("ping")).toBeInTheDocument();
    expect(screen.getByText(/"novato-ca"/)).toBeInTheDocument();
  });

  it("shows an error state when the probe fails", async () => {
    render(
      <McpConnectivityPanel
        client={createMockClient("failure")}
        autoConnect={false}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /connect & probe/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent("Error");
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Connection refused");
  });
});
