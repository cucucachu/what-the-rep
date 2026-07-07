import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithRouter, createMockMcpClient } from "../test/renderWithRouter.js";
import { OfficialPage } from "./OfficialPage.js";

const mockMcpWidget = vi.fn(
  (props: { toolName: string; toolArgs?: Record<string, unknown> }) => (
    <div
      data-testid="official-widget"
      data-tool={props.toolName}
      data-person-id={props.toolArgs?.person_id as string}
    />
  ),
);

vi.mock("../components/McpWidget.js", () => ({
  McpWidget: (props: unknown) => mockMcpWidget(props as never),
}));

describe("OfficialPage", () => {
  beforeEach(() => {
    mockMcpWidget.mockClear();
  });

  it("renders header and invokes McpWidget with get_official", async () => {
    const client = createMockMcpClient({
      get_official: async () => ({
        found: true,
        person: { id: "p1", full_name: "Jane Doe" },
        tenure_history: [
          {
            tenure: { id: "t1" },
            office: { id: "o1", title: "Mayor" },
            jurisdiction: { id: "j1", slug: "novato-ca", name: "City of Novato" },
            governing_body: null,
          },
        ],
        voting_record: [],
      }),
    });

    renderWithRouter(<OfficialPage />, {
      route: "/official/p1",
      path: "/official/:id",
      client,
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /jane doe/i })).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /city of novato/i })).toHaveAttribute(
      "href",
      "/jurisdiction/novato-ca",
    );
    expect(screen.getByTestId("official-widget")).toHaveAttribute("data-tool", "get_official");
    expect(screen.getByTestId("official-widget")).toHaveAttribute("data-person-id", "p1");
  });

  it("shows not found for missing official", async () => {
    const client = createMockMcpClient({
      get_official: async () => ({ found: false, person_id: "bad" }),
    });

    renderWithRouter(<OfficialPage />, {
      route: "/official/bad",
      path: "/official/:id",
      client,
    });

    await waitFor(() => {
      expect(screen.getByText(/not found/i)).toBeInTheDocument();
    });

    expect(screen.queryByTestId("official-widget")).not.toBeInTheDocument();
  });
});
