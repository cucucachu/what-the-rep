import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import { WhatTheRepMcpClient } from "./client.js";

type McpClientContextValue = {
  client: WhatTheRepMcpClient;
};

const McpClientContext = createContext<McpClientContextValue | null>(null);

export type McpClientProviderProps = {
  client?: WhatTheRepMcpClient;
  children: ReactNode;
};

export function McpClientProvider({
  client: clientProp,
  children,
}: McpClientProviderProps) {
  const client = useMemo(
    () => clientProp ?? new WhatTheRepMcpClient(),
    [clientProp],
  );

  const value = useMemo(() => ({ client }), [client]);

  return (
    <McpClientContext.Provider value={value}>
      {children}
    </McpClientContext.Provider>
  );
}

export function useMcpClient(): WhatTheRepMcpClient {
  const context = useContext(McpClientContext);
  if (!context) {
    throw new Error("useMcpClient must be used within McpClientProvider");
  }
  return context.client;
}

export function useOptionalMcpClient(): WhatTheRepMcpClient | null {
  return useContext(McpClientContext)?.client ?? null;
}
