import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, type RenderOptions } from "@testing-library/react";
import { vi } from "vitest";

import { McpClientProvider } from "../mcp/McpClientContext.js";
import { WhatTheRepMcpClient } from "../mcp/client.js";

export function createMockMcpClient(
  handlers: Record<
    string,
    (args: Record<string, unknown>) => unknown | Promise<unknown>
  > = {},
): WhatTheRepMcpClient {
  return {
    connect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(false),
    callTool: vi.fn().mockImplementation(async (name: string, args: Record<string, unknown>) => {
      const handler = handlers[name];
      if (!handler) {
        throw new Error(`Unexpected tool: ${name}`);
      }
      return handler(args);
    }),
    callToolRaw: vi.fn(),
    listTools: vi.fn(),
    readResource: vi.fn(),
    disconnect: vi.fn(),
    getUrl: vi.fn().mockReturnValue("http://127.0.0.1:8000/mcp/"),
    getConnectionStatus: vi.fn().mockReturnValue("idle"),
  } as unknown as WhatTheRepMcpClient;
}

type RenderWithRouterOptions = RenderOptions & {
  route?: string;
  client?: WhatTheRepMcpClient;
  path?: string;
};

export function renderWithRouter(
  ui: ReactElement,
  {
    route = "/",
    client = createMockMcpClient(),
    path = "/",
    ...options
  }: RenderWithRouterOptions = {},
) {
  window.history.pushState({}, "", route);

  return render(
    <McpClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={path} element={ui} />
        </Routes>
      </MemoryRouter>
    </McpClientProvider>,
    options,
  );
}
