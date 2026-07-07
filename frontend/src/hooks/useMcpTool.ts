import { useCallback, useEffect, useState } from "react";

import { useMcpClient } from "../mcp/McpClientContext.js";

export type McpToolState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "not-found" }
  | { status: "error"; message: string };

type FoundResult = { found?: boolean };

export function useMcpTool<T extends FoundResult>(
  toolName: string,
  args: Record<string, unknown>,
  options: { enabled?: boolean } = {},
): McpToolState<T> & { reload: () => void } {
  const client = useMcpClient();
  const enabled = options.enabled ?? true;
  const [state, setState] = useState<McpToolState<T>>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
    setReloadToken((current) => current + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;

    const load = async () => {
      setState({ status: "loading" });

      try {
        if (!client.isConnected()) {
          await client.connect();
        }

        const data = (await client.callTool(toolName, args)) as T;

        if (cancelled) {
          return;
        }

        if (data.found === false) {
          setState({ status: "not-found" });
          return;
        }

        setState({ status: "ready", data });
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Failed to load data";
        setState({ status: "error", message });
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [client, toolName, JSON.stringify(args), enabled, reloadToken]);

  return { ...state, reload };
}
