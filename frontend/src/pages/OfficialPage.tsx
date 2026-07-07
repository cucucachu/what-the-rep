import { Link, useParams } from "react-router-dom";

import { McpWidget } from "../components/McpWidget.js";
import {
  ErrorState,
  LoadingState,
  NotFoundState,
} from "../components/PageStatus.js";
import { useMcpTool } from "../hooks/useMcpTool.js";
import { useMcpClient } from "../mcp/McpClientContext.js";
import "./Pages.css";

type SerializedDoc = {
  id: string;
  full_name?: string;
  slug?: string;
  [key: string]: unknown;
};

type TenureEntry = {
  tenure: SerializedDoc;
  office: SerializedDoc | null;
  jurisdiction: SerializedDoc | null;
  governing_body: SerializedDoc | null;
};

type GetOfficialResult = {
  found: boolean;
  person: SerializedDoc;
  tenure_history: TenureEntry[];
  voting_record: unknown[];
};

export function OfficialPage() {
  const { id = "" } = useParams<{ id: string }>();
  const client = useMcpClient();
  const result = useMcpTool<GetOfficialResult>("get_official", { person_id: id });

  if (result.status === "loading") {
    return <LoadingState title="Official" />;
  }

  if (result.status === "not-found") {
    return (
      <NotFoundState
        title="Official"
        message={`No official found for id "${id}".`}
      />
    );
  }

  if (result.status === "error") {
    return (
      <ErrorState
        title="Official"
        message={result.message}
        onRetry={result.reload}
      />
    );
  }

  const { person, tenure_history } = result.data;
  const name = (person.full_name as string | undefined) ?? "Official";

  return (
    <article className="detail-page" aria-label="Official detail">
      <header className="detail-page__header">
        <p className="detail-page__breadcrumb">
          <Link to="/search">Search</Link>
          <span aria-hidden="true"> / </span>
          <span>{name}</span>
        </p>
        <h2>{name}</h2>
      </header>

      {tenure_history.length > 0 ? (
        <section className="detail-page__section" aria-labelledby="tenure-history">
          <h3 id="tenure-history">Tenure history</h3>
          <ul className="detail-page__list">
            {tenure_history.map(({ tenure, office, jurisdiction }) => (
              <li key={tenure.id}>
                {(office?.title as string | undefined) ?? "Office"}
                {jurisdiction?.slug ? (
                  <>
                    {" at "}
                    <Link to={`/jurisdiction/${jurisdiction.slug}`}>
                      {jurisdiction.name as string}
                    </Link>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="detail-page__section" aria-labelledby="voting-history">
        <h3 id="voting-history">Voting history</h3>
        <McpWidget
          client={client}
          toolName="get_official"
          toolArgs={{ person_id: id }}
        />
      </section>
    </article>
  );
}
