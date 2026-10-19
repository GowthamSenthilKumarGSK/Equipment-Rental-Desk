import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon, type IconName } from "./Icon";

export type Tone = "ok" | "info" | "warn" | "orange" | "danger";

interface StatProps {
  label: string;
  value: string;
  note?: ReactNode;
  /** Semantic colour of the top edge. Same meaning as the status badges on every page. */
  tone?: Tone;
  icon?: IconName;
  /** Makes the whole figure a link, e.g. from "Overdue loans" to the overdue list. */
  to?: string;
}

/** One key figure: a label, the number, and a note that says what it counts or is compared with. */
export function Stat({ label, value, note, tone, icon, to }: StatProps) {
  const className = ["stat", tone && `stat--${tone}`, to && "stat--link"].filter(Boolean).join(" ");
  const text = (
    <>
      {icon && <Icon name={icon} size={16} />}
      {label}
    </>
  );
  return (
    <li className={className}>
      <span className="stat__label">
        {to ? (
          <Link to={to} className="stat__link">
            {text}
          </Link>
        ) : (
          text
        )}
      </span>
      <strong className="stat__value">{value}</strong>
      {note && <span className="stat__note muted">{note}</span>}
    </li>
  );
}

export function Stats({
  label,
  compact = false,
  children,
}: {
  label: string;
  /** Narrower tiles, for a row of five or six short figures. */
  compact?: boolean;
  children: ReactNode;
}) {
  return (
    <ul className={compact ? "stats stats--compact" : "stats"} aria-label={label}>
      {children}
    </ul>
  );
}
