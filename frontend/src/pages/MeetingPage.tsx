import { Link, useParams } from "react-router-dom";

import { ActionLink } from "../components/EntityLinks.js";
import {
  ErrorState,
  LoadingState,
  NotFoundState,
} from "../components/PageStatus.js";
import { useMcpTool } from "../hooks/useMcpTool.js";
import "./Pages.css";

type SerializedDoc = {
  id: string;
  title?: string;
  description?: string;
  item_number?: string;
  scheduled_start?: string;
  url?: string;
  [key: string]: unknown;
};

type AgendaItemPayload = {
  agenda_item: SerializedDoc;
  actions: SerializedDoc[];
  documents: SerializedDoc[];
};

type GetMeetingResult = {
  found: boolean;
  meeting: SerializedDoc;
  governing_body: SerializedDoc | null;
  agenda_items: AgendaItemPayload[];
  meeting_documents: SerializedDoc[];
};

export function MeetingPage() {
  const { id = "" } = useParams<{ id: string }>();
  const result = useMcpTool<GetMeetingResult>("get_meeting", { meeting_id: id });

  if (result.status === "loading") {
    return <LoadingState title="Meeting" />;
  }

  if (result.status === "not-found") {
    return (
      <NotFoundState
        title="Meeting"
        message={`No meeting found for id "${id}".`}
      />
    );
  }

  if (result.status === "error") {
    return (
      <ErrorState
        title="Meeting"
        message={result.message}
        onRetry={result.reload}
      />
    );
  }

  const { meeting, governing_body, agenda_items, meeting_documents } = result.data;

  return (
    <article className="detail-page" aria-label="Meeting detail">
      <header className="detail-page__header">
        <p className="detail-page__breadcrumb">
          <Link to="/search?tab=meetings">Meetings</Link>
          <span aria-hidden="true"> / </span>
          <span>{formatMeetingTitle(meeting)}</span>
        </p>
        <h2>{formatMeetingTitle(meeting)}</h2>
        {governing_body?.name ? (
          <p className="detail-page__meta">{governing_body.name as string}</p>
        ) : null}
      </header>

      <section className="detail-page__section" aria-labelledby="agenda-items">
        <h3 id="agenda-items">Agenda items</h3>
        {agenda_items.length === 0 ? (
          <p className="detail-page__empty">No agenda items listed.</p>
        ) : (
          <ol className="detail-page__agenda">
            {agenda_items.map(({ agenda_item, actions, documents }) => (
              <li key={agenda_item.id} className="detail-page__agenda-item">
                <h4>
                  {agenda_item.item_number ? `${agenda_item.item_number}. ` : ""}
                  {agenda_item.title ?? "Agenda item"}
                </h4>
                {agenda_item.description ? (
                  <p className="detail-page__description">{agenda_item.description}</p>
                ) : null}

                {actions.length > 0 ? (
                  <div className="detail-page__nested">
                    <p className="detail-page__nested-label">Actions</p>
                    <ul className="detail-page__list">
                      {actions.map((action) => (
                        <li key={action.id}>
                          <ActionLink
                            id={action.id}
                            label={actionLabel(action)}
                          />
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {documents.length > 0 ? (
                  <div className="detail-page__nested">
                    <p className="detail-page__nested-label">Documents</p>
                    <ul className="detail-page__list">
                      {documents.map((doc) => (
                        <li key={doc.id}>
                          <DocumentEntry doc={doc} />
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      {meeting_documents.length > 0 ? (
        <section className="detail-page__section" aria-labelledby="meeting-documents">
          <h3 id="meeting-documents">Meeting documents</h3>
          <ul className="detail-page__list">
            {meeting_documents.map((doc) => (
              <li key={doc.id}>
                <DocumentEntry doc={doc} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

function DocumentEntry({ doc }: { doc: SerializedDoc }) {
  const label = (doc.title as string | undefined) ?? doc.id;
  if (typeof doc.url === "string" && doc.url.length > 0) {
    return (
      <a href={doc.url} target="_blank" rel="noopener noreferrer">
        {label}
      </a>
    );
  }
  return <span>{label}</span>;
}

function formatMeetingTitle(meeting: SerializedDoc): string {
  if (meeting.scheduled_start) {
    return formatDate(meeting.scheduled_start);
  }
  return "Meeting";
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
