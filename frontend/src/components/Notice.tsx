import type { ReactNode, Ref } from "react";
import type { ApiError } from "../api";
import { describeError } from "../messages";
import { Icon, type IconName } from "./Icon";
import { SkeletonCards, SkeletonList, SkeletonLines } from "./Skeleton";

interface NoticeProps {
  kind: "success" | "error" | "info";
  children: ReactNode;
  /** Lets a page move focus to this message when the control that caused it has gone. */
  noticeRef?: Ref<HTMLDivElement>;
}

const NOTICE_ICONS: Record<NoticeProps["kind"], IconName> = {
  success: "check",
  error: "warning",
  info: "info",
};

/** Errors are announced to screen readers at once (alert); other messages politely (status). */
export function Notice({ kind, children, noticeRef }: NoticeProps) {
  return (
    <div
      ref={noticeRef}
      tabIndex={-1}
      className={`notice notice--${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      <Icon name={NOTICE_ICONS[kind]} />
      <div className="notice__body">{children}</div>
    </div>
  );
}

export function ErrorNotice({
  error,
  onRetry,
  noticeRef,
}: {
  error: ApiError;
  onRetry?: () => void;
  noticeRef?: Ref<HTMLDivElement>;
}) {
  const view = describeError(error);
  return (
    <Notice kind="error" noticeRef={noticeRef}>
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
          <Icon name="refresh" size={16} />
          Try again
        </button>
      )}
    </Notice>
  );
}

type Placeholder = "list" | "cards" | "lines" | "none";

/**
 * The one "loading" message of a screen: a polite status with the words, and grey placeholder
 * shapes (hidden from assistive technology) that show roughly what is coming.
 */
export function Loading({ what, shape = "lines" }: { what: string; shape?: Placeholder }) {
  return (
    <div className="loading" role="status">
      <p className="muted">Loading {what}…</p>
      {shape === "list" && <SkeletonList />}
      {shape === "cards" && <SkeletonCards />}
      {shape === "lines" && <SkeletonLines />}
    </div>
  );
}
