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
  title?: string;
  description?: string;
  item_number?: string;
  scheduled_start?: string;
  [key: string]: unknown;
};

type GetActionResult = {
  found: boolean;
  action: SerializedDoc;
  meeting: SerializedDoc | null;
  agenda_item: SerializedDoc | null;
  vote_records: unknown[];
  documents: SerializedDoc[];
};

export function ActionPage() {
  const { id = "" } = useParams<{ id: string }>();
  const client = useMcpClient();
  const result = useMcpTool<GetActionResult>("get_action", { action_id: id });

  if (result.status === "loading") {
    return <LoadingState title="Action" />;
  }

  if (result.status === "not-found") {
    return (
      <NotFoundState
        title="Action"
        message={`No action found for id "${id}".`}
      />
    );
  }

  if (result.status === "error") {
    return (
      <ErrorState
        title="Action"
        message={result.message}
        onRetry={result.reload}
      />
    );
  }

  const { action, meeting, agenda_item } = result.data;

  return (
    <article className="detail-page" aria-label="Action detail">
      <header className="detail-page__header">
        <p className="detail-page__breadcrumb">
          <Link to="/search?tab=actions">Actions</Link>
          <span aria-hidden="true"> / </span>
          <span>{actionLabel(action)}</span>
        </p>
        <h2>{actionLabel(action)}</h2>
        {action.outcome ? (
          <p className="detail-page__meta">Outcome: {String(action.outcome)}</p>
        ) : null}
      </header>

      <section className="detail-page__section" aria-labelledby="action-context">
        <h3 id="action-context">Context</h3>
        <ul className="detail-page__list">
          {meeting ? (
            <li>
              Meeting:{" "}
              <Link to={`/meeting/${meeting.id}`}>
                {meeting.scheduled_start
                  ? formatDate(meeting.scheduled_start as string)
                  : meeting.id}
              </Link>
            </li>
          ) : null}
          {agenda_item ? (
            <li>
              Agenda item:{" "}
              {agenda_item.item_number ? `${agenda_item.item_number}. ` : ""}
              {agenda_item.title ?? agenda_item.id}
            </li>
          ) : null}
        </ul>
      </section>

      <section className="detail-page__section" aria-labelledby="vote-tally">
        <h3 id="vote-tally">Vote tally</h3>
        <McpWidget
          client={client}
          toolName="get_action"
          toolArgs={{ action_id: id }}
        />
      </section>
    </article>
  );
}

function actionLabel(action: SerializedDoc): string {
  if (action.description) {
    return action.description as string;
  }
  if (action.action_type) {
    return String(action.action_type);
  }
  return `Action ${action.id.slice(0, 8)}`;
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
