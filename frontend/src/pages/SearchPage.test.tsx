import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithRouter, createMockMcpClient } from "../test/renderWithRouter.js";
import { SearchPage } from "./SearchPage.js";

describe("SearchPage", () => {
  it("lists jurisdictions with links to detail pages", async () => {
    const client = createMockMcpClient({
      list_jurisdictions: async () => ({
        jurisdictions: [
          { id: "j1", slug: "novato-ca", name: "City of Novato" },
        ],
        count: 1,
      }),
    });

    renderWithRouter(<SearchPage />, {
      route: "/search?tab=jurisdictions",
      path: "/search",
      client,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /city of novato/i })).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /city of novato/i })).toHaveAttribute(
      "href",
      "/jurisdiction/novato-ca",
    );
  });

  it("searches actions and links to action detail pages", async () => {
    const user = userEvent.setup();
    const client = createMockMcpClient({
      search_actions: async () => ({
        actions: [{ id: "act1", description: "Approve budget" }],
        count: 1,
      }),
      list_jurisdictions: async () => ({ jurisdictions: [], count: 0 }),
    });

    renderWithRouter(<SearchPage />, {
      route: "/search?tab=actions",
      path: "/search",
      client,
    });

    await user.click(screen.getByRole("tab", { name: /actions/i }));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /approve budget/i })).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /approve budget/i })).toHaveAttribute(
      "href",
      "/action/act1",
    );
  });
});
