import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithRouter, createMockMcpClient } from "../test/renderWithRouter.js";
import { ActionPage } from "./ActionPage.js";

const mockMcpWidget = vi.fn(
  (props: { toolName: string; toolArgs?: Record<string, unknown> }) => (
    <div
      data-testid="action-widget"
      data-tool={props.toolName}
      data-action-id={props.toolArgs?.action_id as string}
    />
  ),
);

vi.mock("../components/McpWidget.js", () => ({
  McpWidget: (props: unknown) => mockMcpWidget(props as never),
}));

describe("ActionPage", () => {
  beforeEach(() => {
    mockMcpWidget.mockClear();
  });

  it("renders context and invokes McpWidget with get_action", async () => {
    const client = createMockMcpClient({
      get_action: async () => ({
        found: true,
        action: {
          id: "act1",
          description: "Approve budget",
          outcome: "passed",
        },
        meeting: { id: "m1", scheduled_start: "2026-06-01T18:00:00Z" },
        agenda_item: { id: "ai1", item_number: "C.2", title: "Budget item" },
        vote_records: [],
        documents: [],
      }),
    });

    renderWithRouter(<ActionPage />, {
      route: "/action/act1",
      path: "/action/:id",
      client,
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /approve budget/i })).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /june/i })).toHaveAttribute("href", "/meeting/m1");
    expect(screen.getByTestId("action-widget")).toHaveAttribute("data-tool", "get_action");
    expect(screen.getByTestId("action-widget")).toHaveAttribute("data-action-id", "act1");
  });

  it("shows not found for missing action", async () => {
    const client = createMockMcpClient({
      get_action: async () => ({ found: false, action_id: "bad" }),
    });

    renderWithRouter(<ActionPage />, {
      route: "/action/bad",
      path: "/action/:id",
      client,
    });

    await waitFor(() => {
      expect(screen.getByText(/not found/i)).toBeInTheDocument();
    });

    expect(screen.queryByTestId("action-widget")).not.toBeInTheDocument();
  });
});
