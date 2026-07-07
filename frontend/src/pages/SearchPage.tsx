import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  ErrorState,
  LoadingState,
} from "../components/PageStatus.js";
import { useMcpClient } from "../mcp/McpClientContext.js";
import "./Pages.css";

type SerializedDoc = {
  id: string;
  name?: string;
  slug?: string;
  title?: string;
  description?: string;
  scheduled_start?: string;
  outcome?: string;
  [key: string]: unknown;
};

type SearchTab = "jurisdictions" | "meetings" | "actions";

type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; results: SerializedDoc[]; count: number }
  | { status: "error"; message: string };

const TAB_LABELS: Record<SearchTab, string> = {
  jurisdictions: "Jurisdictions",
  meetings: "Meetings",
  actions: "Actions",
};

export function SearchPage() {
  const client = useMcpClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = parseTab(searchParams.get("tab"));
  const initialJurisdiction = searchParams.get("jurisdiction") ?? "";
  const initialQuery = searchParams.get("q") ?? "";

  const [tab, setTab] = useState<SearchTab>(initialTab);
  const [query, setQuery] = useState(initialQuery);
  const [jurisdictionSlug, setJurisdictionSlug] = useState(initialJurisdiction);
  const [state, setState] = useState<SearchState>({ status: "idle" });

  const runSearch = useCallback(async () => {
    setState({ status: "loading" });

    try {
      if (!client.isConnected()) {
        await client.connect();
      }

      let results: SerializedDoc[] = [];
      let count = 0;

      if (tab === "jurisdictions") {
        const payload = (await client.callTool("list_jurisdictions", {
          parent_slug: jurisdictionSlug || undefined,
        })) as { jurisdictions: SerializedDoc[]; count: number };
        results = payload.jurisdictions;
        count = payload.count;
        if (query.trim()) {
          const normalized = query.trim().toLowerCase();
          results = results.filter((item) =>
            (item.name ?? "").toLowerCase().includes(normalized),
          );
          count = results.length;
        }
      } else if (tab === "meetings") {
        const payload = (await client.callTool("search_meetings", {
          jurisdiction_slug: jurisdictionSlug || undefined,
          query: query.trim() || undefined,
        })) as { meetings: SerializedDoc[]; count: number };
        results = payload.meetings;
        count = payload.count;
      } else {
        const payload = (await client.callTool("search_actions", {
          jurisdiction_slug: jurisdictionSlug || undefined,
          query: query.trim() || undefined,
        })) as { actions: SerializedDoc[]; count: number };
        results = payload.actions;
        count = payload.count;
      }

      setState({ status: "ready", results, count });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Search failed";
      setState({ status: "error", message });
    }
  }, [client, tab, query, jurisdictionSlug]);

  useEffect(() => {
    void runSearch();
  }, [runSearch]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const params = new URLSearchParams();
    params.set("tab", tab);
    if (query.trim()) {
      params.set("q", query.trim());
    }
    if (jurisdictionSlug.trim()) {
      params.set("jurisdiction", jurisdictionSlug.trim());
    }
    setSearchParams(params);
    void runSearch();
  };

  const handleTabChange = (nextTab: SearchTab) => {
    setTab(nextTab);
    const params = new URLSearchParams(searchParams);
    params.set("tab", nextTab);
    setSearchParams(params);
  };

  return (
    <section className="search-page" aria-label="Search">
      <header className="detail-page__header">
        <h2>Search</h2>
        <p className="detail-page__meta">
          Browse jurisdictions, meetings, and actions across the pilot area.
        </p>
      </header>

      <div className="search-page__tabs" role="tablist" aria-label="Search type">
        {(Object.keys(TAB_LABELS) as SearchTab[]).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "search-page__tab search-page__tab--active" : "search-page__tab"}
            onClick={() => handleTabChange(key)}
          >
            {TAB_LABELS[key]}
          </button>
        ))}
      </div>

      <form className="search-page__form" onSubmit={handleSubmit} aria-label="Search filters">
        <label>
          Query
          <input
            type="search"
            name="q"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={
              tab === "jurisdictions" ? "Filter by name…" : "Search text…"
            }
          />
        </label>
        <label>
          Jurisdiction slug
          <input
            type="text"
            name="jurisdiction"
            value={jurisdictionSlug}
            onChange={(event) => setJurisdictionSlug(event.target.value)}
            placeholder="e.g. novato-ca"
          />
        </label>
        <button type="submit">Search</button>
      </form>

      {state.status === "loading" ? <LoadingState title="Search results" /> : null}

      {state.status === "error" ? (
        <ErrorState title="Search results" message={state.message} onRetry={runSearch} />
      ) : null}

      {state.status === "ready" ? (
        <section className="search-page__results" aria-live="polite">
          <p className="search-page__count">
            {state.count} result{state.count === 1 ? "" : "s"}
          </p>
          {state.results.length === 0 ? (
            <p className="detail-page__empty">No results found.</p>
          ) : (
            <ul className="detail-page__list">
              {state.results.map((item) => (
                <li key={item.id}>{renderResultLink(tab, item)}</li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </section>
  );
}

function parseTab(value: string | null): SearchTab {
  if (value === "meetings" || value === "actions" || value === "jurisdictions") {
    return value;
  }
  return "jurisdictions";
}

function renderResultLink(tab: SearchTab, item: SerializedDoc) {
  if (tab === "jurisdictions" && item.slug) {
    return <Link to={`/jurisdiction/${item.slug}`}>{item.name ?? item.slug}</Link>;
  }
  if (tab === "meetings") {
    const label = item.scheduled_start
      ? formatDate(item.scheduled_start as string)
      : item.title ?? item.id;
    return <Link to={`/meeting/${item.id}`}>{label}</Link>;
  }
  const label =
    (item.description as string | undefined) ??
    (item.title as string | undefined) ??
    item.id;
  return <Link to={`/action/${item.id}`}>{label}</Link>;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}
