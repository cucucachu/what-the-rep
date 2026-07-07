import { Link } from "react-router-dom";

type PageStatusProps = {
  title: string;
  message?: string;
};

export function LoadingState({ title }: { title: string }) {
  return (
    <section className="page-status" aria-label={title}>
      <p className="page-status__message" role="status">
        Loading…
      </p>
    </section>
  );
}

export function NotFoundState({ title, message }: PageStatusProps) {
  return (
    <section className="page-status page-status--not-found" aria-label={title}>
      <h2>Not found</h2>
      <p className="page-status__message">
        {message ?? "We could not find what you were looking for."}
      </p>
      <Link to="/" className="page-status__link">
        Back to home
      </Link>
    </section>
  );
}

export function ErrorState({
  title,
  message,
  onRetry,
}: PageStatusProps & { onRetry?: () => void }) {
  return (
    <section className="page-status page-status--error" aria-label={title}>
      <h2>Something went wrong</h2>
      <p className="page-status__message" role="alert">
        {message ?? "An unexpected error occurred."}
      </p>
      <div className="page-status__actions">
        {onRetry ? (
          <button type="button" onClick={onRetry}>
            Try again
          </button>
        ) : null}
        <Link to="/" className="page-status__link">
          Back to home
        </Link>
      </div>
    </section>
  );
}
