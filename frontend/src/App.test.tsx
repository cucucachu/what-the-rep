import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./pages/HomePage.js", () => ({
  HomePage: () => <section aria-label="Home page">Home page</section>,
}));

vi.mock("./components/McpConnectivityPanel.js", () => ({
  McpConnectivityPanel: () => (
    <section aria-label="MCP connectivity probe">MCP panel</section>
  ),
}));

describe("App", () => {
  it("renders the home page by default", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { name: /what the rep/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/home page/i)).toBeInTheDocument();
    expect(
      screen.queryByLabelText(/mcp connectivity probe/i),
    ).not.toBeInTheDocument();
  });

  it("can toggle the dev MCP probe panel", async () => {
    render(<App />);

    await userEvent.click(
      screen.getByRole("button", { name: /show mcp probe/i }),
    );

    expect(screen.getByLabelText(/mcp connectivity probe/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/home page/i)).not.toBeInTheDocument();
  });
});
