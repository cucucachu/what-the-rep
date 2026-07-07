import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithRouter, createMockMcpClient } from "../test/renderWithRouter.js";
import { JurisdictionPage } from "./JurisdictionPage.js";

describe("JurisdictionPage", () => {
  it("renders jurisdiction profile with officeholder and search links", async () => {
    const client = createMockMcpClient({
      get_jurisdiction: async () => ({
        found: true,
        jurisdiction: {
          id: "j1",
          slug: "novato-ca",
          name: "City of Novato",
          level: "city",
        },
        governing_bodies: [{ id: "b1", name: "City Council" }],
        current_officeholders: [
          {
            office: { id: "o1", title: "Mayor" },
            person: { id: "p1", full_name: "Jane Doe" },
            tenure: { id: "t1" },
          },
        ],
        recent_activity: {
          meetings_count_90d: 3,
          latest_meeting: { id: "m1", scheduled_start: "2026-06-01T18:00:00Z" },
        },
      }),
    });

    renderWithRouter(<JurisdictionPage />, {
      route: "/jurisdiction/novato-ca",
      path: "/jurisdiction/:slug",
      client,
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /city of novato/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/city council/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /jane doe/i })).toHaveAttribute(
      "href",
      "/official/p1",
    );
    expect(screen.getByRole("link", { name: /search meetings/i })).toHaveAttribute(
      "href",
      "/search?tab=meetings&jurisdiction=novato-ca",
    );
    expect(screen.getByRole("link", { name: /search actions/i })).toHaveAttribute(
      "href",
      "/search?tab=actions&jurisdiction=novato-ca",
    );
  });

  it("shows not found for missing jurisdiction", async () => {
    const client = createMockMcpClient({
      get_jurisdiction: async () => ({ found: false, slug: "missing" }),
    });

    renderWithRouter(<JurisdictionPage />, {
      route: "/jurisdiction/missing",
      path: "/jurisdiction/:slug",
      client,
    });

    await waitFor(() => {
      expect(screen.getByText(/not found/i)).toBeInTheDocument();
    });
  });
});
