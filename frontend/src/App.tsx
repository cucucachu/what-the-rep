import { McpConnectivityPanel } from "./components/McpConnectivityPanel.js";

export default function App() {
  return (
    <main className="app">
      <h1>What The Rep</h1>
      <p>Civic transparency platform — MCP host connectivity probe.</p>
      <McpConnectivityPanel />
    </main>
  );
}
