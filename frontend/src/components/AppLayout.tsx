import { Link, Outlet } from "react-router-dom";

export type AppLayoutProps = {
  showDevToggle?: boolean;
  devPanel?: React.ReactNode;
  onToggleDevPanel?: () => void;
  devPanelOpen?: boolean;
};

export function AppLayout({
  showDevToggle = false,
  devPanel,
  onToggleDevPanel,
  devPanelOpen = false,
}: AppLayoutProps) {
  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <Link to="/" className="app__title-link">
            <h1>What The Rep</h1>
          </Link>
          <p>Civic transparency for your local governments.</p>
        </div>
        <nav className="app__nav" aria-label="Main navigation">
          <Link to="/search">Search</Link>
          {showDevToggle && onToggleDevPanel ? (
            <button
              type="button"
              className="app__dev-toggle"
              onClick={onToggleDevPanel}
            >
              {devPanelOpen ? "Hide MCP probe" : "Show MCP probe"}
            </button>
          ) : null}
        </nav>
      </header>

      {devPanelOpen && devPanel ? devPanel : <Outlet />}
    </div>
  );
}
