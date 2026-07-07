import { Link, useParams } from "react-router-dom";

import { OfficialLink } from "../components/EntityLinks.js";
import {
  ErrorState,
  LoadingState,
  NotFoundState,
} from "../components/PageStatus.js";
import { useMcpTool } from "../hooks/useMcpTool.js";
import "./Pages.css";

type SerializedDoc = {
  id: string;
  name?: string;
  slug?: string;
  title?: string;
  level?: string;
  scheduled_start?: string;
  [key: string]: unknown;
};

type GetJurisdictionResult = {
  found: boolean;
  jurisdiction: SerializedDoc;
  governing_bodies: SerializedDoc[];
  current_officeholders: Array<{
    office: SerializedDoc;
    person: SerializedDoc;
    tenure: SerializedDoc;
  }>;
  recent_activity: {
    meetings_count_90d: number;
    latest_meeting: SerializedDoc | null;
  };
};

export function JurisdictionPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const result = useMcpTool<GetJurisdictionResult>("get_jurisdiction", { slug });

  if (result.status === "loading") {
    return <LoadingState title="Jurisdiction" />;
  }

  if (result.status === "not-found") {
    return (
      <NotFoundState
        title="Jurisdiction"
        message={`No jurisdiction found for "${slug}".`}
      />
    );
  }

  if (result.status === "error") {
    return (
      <ErrorState
        title="Jurisdiction"
        message={result.message}
        onRetry={result.reload}
      />
    );
  }

  const { jurisdiction, governing_bodies, current_officeholders, recent_activity } =
    result.data;

  return (
    <article className="detail-page" aria-label="Jurisdiction detail">
      <header className="detail-page__header">
        <p className="detail-page__breadcrumb">
          <Link to="/search">Search</Link>
          <span aria-hidden="true"> / </span>
          <span>{jurisdiction.name}</span>
        </p>
        <h2>{jurisdiction.name}</h2>
        {jurisdiction.level ? (
          <p className="detail-page__meta">Level: {jurisdiction.level}</p>
        ) : null}
      </header>

      <section className="detail-page__section" aria-labelledby="governing-bodies">
        <h3 id="governing-bodies">Governing bodies</h3>
        {governing_bodies.length === 0 ? (
          <p className="detail-page__empty">No governing bodies listed.</p>
        ) : (
          <ul className="detail-page__list">
            {governing_bodies.map((body) => (
              <li key={body.id}>{body.name ?? body.title ?? body.id}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="detail-page__section" aria-labelledby="officeholders">
        <h3 id="officeholders">Current officeholders</h3>
        {current_officeholders.length === 0 ? (
          <p className="detail-page__empty">No current officeholders listed.</p>
        ) : (
          <ul className="detail-page__list">
            {current_officeholders.map(({ office, person }) => (
              <li key={`${office.id}-${person.id}`}>
                {person.full_name ? (
                  <OfficialLink id={person.id} name={person.full_name as string} />
                ) : (
                  <span>Unknown official</span>
                )}
                {" — "}
                {office.title ?? "Office"}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="detail-page__section" aria-labelledby="recent-activity">
        <h3 id="recent-activity">Recent activity</h3>
        <p>
          {recent_activity.meetings_count_90d} meeting
          {recent_activity.meetings_count_90d === 1 ? "" : "s"} in the last 90 days.
        </p>
        {recent_activity.latest_meeting ? (
          <p>
            Latest meeting:{" "}
            <Link to={`/meeting/${recent_activity.latest_meeting.id}`}>
              {formatDate(recent_activity.latest_meeting.scheduled_start)}
            </Link>
          </p>
        ) : null}
      </section>

      <section className="detail-page__section" aria-labelledby="explore">
        <h3 id="explore">Explore</h3>
        <ul className="detail-page__links">
          <li>
            <Link to={`/search?tab=meetings&jurisdiction=${slug}`}>
              Search meetings in {jurisdiction.name}
            </Link>
          </li>
          <li>
            <Link to={`/search?tab=actions&jurisdiction=${slug}`}>
              Search actions in {jurisdiction.name}
            </Link>
          </li>
        </ul>
      </section>
    </article>
  );
}

function formatDate(value: unknown): string {
  if (typeof value !== "string") {
    return "Meeting";
  }
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
