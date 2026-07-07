import { useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout.js";
import { McpConnectivityPanel } from "./components/McpConnectivityPanel.js";
import { ActionPage } from "./pages/ActionPage.js";
import { HomePage } from "./pages/HomePage.js";
import { JurisdictionPage } from "./pages/JurisdictionPage.js";
import { MeetingPage } from "./pages/MeetingPage.js";
import { OfficialPage } from "./pages/OfficialPage.js";
import { SearchPage } from "./pages/SearchPage.js";
import { McpClientProvider } from "./mcp/McpClientContext.js";
import "./App.css";

export default function App() {
  const [showDevPanel, setShowDevPanel] = useState(false);
  const isDev = import.meta.env.DEV;

  return (
    <McpClientProvider>
      <BrowserRouter>
        <Routes>
          <Route
            element={
              <AppLayout
                showDevToggle={isDev}
                devPanelOpen={showDevPanel}
                onToggleDevPanel={() => setShowDevPanel((current) => !current)}
                devPanel={<McpConnectivityPanel autoConnect={false} />}
              />
            }
          >
            <Route index element={<HomePage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="jurisdiction/:slug" element={<JurisdictionPage />} />
            <Route path="meeting/:id" element={<MeetingPage />} />
            <Route path="action/:id" element={<ActionPage />} />
            <Route path="official/:id" element={<OfficialPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </McpClientProvider>
  );
}
