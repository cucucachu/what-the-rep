import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithRouter, createMockMcpClient } from "../test/renderWithRouter.js";
import { MeetingPage } from "./MeetingPage.js";

describe("MeetingPage", () => {
  it("renders meeting agenda items with action links", async () => {
    const client = createMockMcpClient({
      get_meeting: async () => ({
        found: true,
        meeting: {
          id: "m1",
          scheduled_start: "2026-06-01T18:00:00Z",
        },
        governing_body: { id: "b1", name: "City Council" },
        agenda_items: [
          {
            agenda_item: {
              id: "a1",
              item_number: "G.1",
              title: "Approve minutes",
            },
            actions: [
              {
                id: "act1",
                description: "Motion to approve minutes",
              },
            ],
            documents: [{ id: "d1", title: "Minutes PDF", url: "https://example.com/minutes.pdf" }],
          },
        ],
        meeting_documents: [],
      }),
    });

    renderWithRouter(<MeetingPage />, {
      route: "/meeting/m1",
      path: "/meeting/:id",
      client,
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 4, name: /approve minutes/i })).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /motion to approve minutes/i })).toHaveAttribute(
      "href",
      "/action/act1",
    );
    expect(screen.getByRole("link", { name: /minutes pdf/i })).toHaveAttribute(
      "href",
      "https://example.com/minutes.pdf",
    );
  });

  it("shows not found for missing meeting", async () => {
    const client = createMockMcpClient({
      get_meeting: async () => ({ found: false, meeting_id: "bad" }),
    });

    renderWithRouter(<MeetingPage />, {
      route: "/meeting/bad",
      path: "/meeting/:id",
      client,
    });

    await waitFor(() => {
      expect(screen.getByText(/not found/i)).toBeInTheDocument();
    });
  });
});
