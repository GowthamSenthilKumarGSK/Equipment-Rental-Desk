import type { ReactNode } from "react";
import type { ApiError } from "../api";
import { describeError } from "../messages";

interface NoticeProps {
  kind: "success" | "error" | "info";
  children: ReactNode;
}

/** Errors are announced to screen readers at once (alert); other messages politely (status). */
export function Notice({ kind, children }: NoticeProps) {
  return (
    <div className={`notice notice--${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const view = describeError(error);
  return (
    <Notice kind="error">
      <strong>{view.title}</strong>
      <p>{view.message}</p>
      {view.lines.length > 0 && (
        <ul>
          {view.lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {view.reference && <p className="muted">Reference: {view.reference}</p>}
      {onRetry && (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </Notice>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <p className="muted" role="status">
      Loading {what}…
    </p>
  );
}
