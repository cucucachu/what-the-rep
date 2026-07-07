export const DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp/";

export function getMcpUrl(): string {
  const configured = import.meta.env.VITE_MCP_URL;
  return configured && configured.trim() !== "" ? configured : DEFAULT_MCP_URL;
}
