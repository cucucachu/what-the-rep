import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./components/McpConnectivityPanel.js", () => ({
  McpConnectivityPanel: () => (
    <section aria-label="MCP connectivity probe">MCP panel</section>
  ),
}));

describe("App", () => {
  it("renders the app heading", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { name: /what the rep/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/mcp connectivity probe/i)).toBeInTheDocument();
  });
});
