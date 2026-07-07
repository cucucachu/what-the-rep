import { useCallback, useEffect, useMemo, useState } from "react";

import { WhatTheRepMcpClient } from "../mcp/client.js";
import type { McpToolInfo } from "../mcp/types.js";
import "./McpConnectivityPanel.css";

export type McpConnectivityPanelProps = {
  client?: WhatTheRepMcpClient;
  autoConnect?: boolean;
  demoToolName?: string;
};

type PanelState = {
  status: "idle" | "connecting" | "connected" | "error";
  tools: McpToolInfo[];
  toolResult: unknown;
  errorMessage: string | null;
};

const initialPanelState: PanelState = {
  status: "idle",
  tools: [],
  toolResult: null,
  errorMessage: null,
};

export function McpConnectivityPanel({
  client: clientProp,
  autoConnect = true,
  demoToolName = "list_jurisdictions",
}: McpConnectivityPanelProps) {
  const client = useMemo(
    () => clientProp ?? new WhatTheRepMcpClient(),
    [clientProp],
  );
  const [state, setState] = useState<PanelState>(initialPanelState);

  const runProbe = useCallback(async () => {
    setState((current) => ({
      ...current,
      status: "connecting",
      errorMessage: null,
      toolResult: null,
    }));

    try {
      await client.connect();
      const [tools, toolResult] = await Promise.all([
        client.listTools(),
        client.callTool(demoToolName),
      ]);

      setState({
        status: "connected",
        tools,
        toolResult,
        errorMessage: null,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown MCP error";
      setState({
        status: "error",
        tools: [],
        toolResult: null,
        errorMessage: message,
      });
    }
  }, [client, demoToolName]);

  useEffect(() => {
    if (autoConnect) {
      void runProbe();
    }
  }, [autoConnect, runProbe]);

  const statusLabel =
    state.status === "connecting"
      ? "Connecting…"
      : state.status === "connected"
        ? "Connected"
        : state.status === "error"
          ? "Error"
          : "Idle";

  return (
    <section className="mcp-panel" aria-label="MCP connectivity probe">
      <header className="mcp-panel__header">
        <div>
          <h2>MCP connectivity</h2>
          <p className="mcp-panel__url">{client.getUrl()}</p>
        </div>
        <div className="mcp-panel__controls">
          <span
            className={`mcp-panel__status mcp-panel__status--${state.status}`}
            role="status"
          >
            {statusLabel}
          </span>
          <button type="button" onClick={() => void runProbe()}>
            {state.status === "connecting" ? "Connecting…" : "Connect & probe"}
          </button>
        </div>
      </header>

      {state.errorMessage ? (
        <p className="mcp-panel__error" role="alert">
          {state.errorMessage}
        </p>
      ) : null}

      {state.status === "connecting" ? (
        <p className="mcp-panel__loading">Loading tools and sample result…</p>
      ) : null}

      {state.tools.length > 0 ? (
        <div className="mcp-panel__section">
          <h3>Available tools ({state.tools.length})</h3>
          <ul className="mcp-panel__tool-list">
            {state.tools.map((tool) => (
              <li key={tool.name}>
                <code>{tool.name}</code>
                {tool.description ? (
                  <span className="mcp-panel__tool-desc">
                    {" "}
                    — {tool.description}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {state.toolResult !== null ? (
        <div className="mcp-panel__section">
          <h3>
            Raw result from <code>{demoToolName}</code>
          </h3>
          <pre className="mcp-panel__json">
            {JSON.stringify(state.toolResult, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
