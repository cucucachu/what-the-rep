import { useState } from "react";

import { McpConnectivityPanel } from "./components/McpConnectivityPanel.js";
import { HomePage } from "./pages/HomePage.js";

export default function App() {
  const [showDevPanel, setShowDevPanel] = useState(false);
  const isDev = import.meta.env.DEV;

  return (
    <main className="app">
      <header className="app__header">
        <div>
          <h1>What The Rep</h1>
          <p>Civic transparency for your local governments.</p>
        </div>
        {isDev ? (
          <button
            type="button"
            className="app__dev-toggle"
            onClick={() => setShowDevPanel((current) => !current)}
          >
            {showDevPanel ? "Hide MCP probe" : "Show MCP probe"}
          </button>
        ) : null}
      </header>

      {showDevPanel ? (
        <McpConnectivityPanel autoConnect={false} />
      ) : (
        <HomePage />
      )}
    </main>
  );
}
