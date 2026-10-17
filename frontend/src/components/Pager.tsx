import { pluralise } from "../format";
import { lastOffset } from "../paging";
import { Notice } from "./Notice";

interface PagerProps {
  total: number;
  limit: number;
  offset: number;
  noun: string;
  onOffsetChange: (offset: number) => void;
}

/** "Showing 1–12 of 40" with Previous and Next. Nothing at all for an empty list or a page past the end. */
export function Pager({ total, limit, offset, noun, onOffsetChange }: PagerProps) {
  if (total === 0 || offset >= total) return null;
  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  return (
    <nav className="pager" aria-label={`${noun} pages`}>
      <p className="muted">
        Showing {first}–{last} of {total}
      </p>
      <div className="pager__buttons">
        <button
          type="button"
          className="button button--secondary"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <button
          type="button"
          className="button button--secondary"
          disabled={last >= total}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}

interface PastTheEndProps {
  total: number;
  limit: number;
  /** What the list holds, lower case and singular: "item", "member", "overdue loan". */
  what: string;
  onOffsetChange: (offset: number) => void;
}

/** Shown instead of the list when the page asked for starts after the last record (a stale link). */
export function PastTheEnd({ total, limit, what, onOffsetChange }: PastTheEndProps) {
  return (
    <Notice kind="info">
      <p>There is nothing on this page. The list has {pluralise(total, what)}.</p>
      <button
        type="button"
        className="button button--secondary"
        onClick={() => onOffsetChange(lastOffset(total, limit))}
      >
        Go to the last page
      </button>
    </Notice>
  );
}
