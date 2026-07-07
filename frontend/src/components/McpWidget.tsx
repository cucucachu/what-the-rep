import { AppRenderer } from "@mcp-ui/client";
import type { CallToolRequest, CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { useCallback, useEffect, useMemo, useState } from "react";

import { WhatTheRepMcpClient } from "../mcp/client.js";
import type { McpResourceContent } from "../mcp/types.js";
import { findToolUiResourceUri, getSandboxProxyUrl } from "../mcp/ui-resource.js";
import "./McpWidget.css";

const EMPTY_TOOL_ARGS: Record<string, unknown> = {};

export type McpWidgetProps = {
  client: WhatTheRepMcpClient;
  toolName: string;
  toolArgs?: Record<string, unknown>;
  /** Pre-resolved `ui://` URI (skips listTools lookup). */
  resourceUri?: string;
  /** Pre-fetched widget HTML (skips readResource; tool is still called unless skipped). */
  html?: string;
  /** Skip initial tool call when html + resourceUri are supplied externally. */
  skipToolCall?: boolean;
  sandboxUrl?: URL;
};

type WidgetState =
  | { status: "loading" }
  | { status: "ready"; resourceUri: string; html: string; toolResult: CallToolResult }
  | { status: "error"; message: string };

export function McpWidget({
  client,
  toolName,
  toolArgs = EMPTY_TOOL_ARGS,
  resourceUri: resourceUriProp,
  html: htmlProp,
  skipToolCall = false,
  sandboxUrl,
}: McpWidgetProps) {
  const [state, setState] = useState<WidgetState>({ status: "loading" });
  const sandbox = useMemo(
    () => ({ url: sandboxUrl ?? getSandboxProxyUrl() }),
    [sandboxUrl],
  );

  useEffect(() => {
    let cancelled = false;

    const loadWidget = async () => {
      setState({ status: "loading" });

      try {
        let toolResult: CallToolResult = { content: [] };
        if (!skipToolCall) {
          toolResult = await client.callToolRaw(toolName, toolArgs);
          if (toolResult.isError) {
            throw new Error(
              toolResult.content
                ?.filter((item) => item.type === "text")
                .map((item) => item.text)
                .join("\n")
                .trim() || `${toolName} failed`,
            );
          }
        }

        let resourceUri = resourceUriProp ?? null;
        if (!resourceUri) {
          const tools = await client.listTools();
          resourceUri = findToolUiResourceUri(tools, toolName);
        }

        if (!resourceUri) {
          throw new Error(`Tool ${toolName} has no linked ui:// resource`);
        }

        let html = htmlProp;
        if (!html) {
          const resource: McpResourceContent = await client.readResource(resourceUri);
          html = resource.text;
        }

        if (cancelled) {
          return;
        }

        setState({
          status: "ready",
          resourceUri,
          html,
          toolResult,
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Failed to load MCP widget";
        setState({ status: "error", message });
      }
    };

    void loadWidget();

    return () => {
      cancelled = true;
    };
  }, [
    client,
    toolName,
    JSON.stringify(toolArgs),
    resourceUriProp,
    htmlProp,
    skipToolCall,
  ]);

  const handleCallTool = useCallback(
    async (params: CallToolRequest["params"]): Promise<CallToolResult> => {
      return client.callToolRaw(params.name, params.arguments ?? {});
    },
    [client],
  );

  if (state.status === "loading") {
    return (
      <section className="mcp-widget" aria-label={`${toolName} widget`}>
        <p className="mcp-widget__loading" role="status">
          Loading widget…
        </p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="mcp-widget" aria-label={`${toolName} widget`}>
        <p className="mcp-widget__error" role="alert">
          {state.message}
        </p>
      </section>
    );
  }

  return (
    <section className="mcp-widget" aria-label={`${toolName} widget`}>
      <div className="mcp-widget__frame">
        <AppRenderer
          toolName={toolName}
          sandbox={sandbox}
          html={state.html}
          toolResourceUri={state.resourceUri}
          toolInput={toolArgs}
          toolResult={state.toolResult}
          onCallTool={handleCallTool}
          onOpenLink={async ({ url }) => {
            if (url.startsWith("http://") || url.startsWith("https://")) {
              window.open(url, "_blank", "noopener,noreferrer");
            }
            return {};
          }}
          onError={(error) => {
            setState({ status: "error", message: error.message });
          }}
        />
      </div>
    </section>
  );
}
