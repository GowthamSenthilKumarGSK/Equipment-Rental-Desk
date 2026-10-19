import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

/** An empty list says what is missing and, when there is one, offers the obvious next step. */
export function EmptyState({
  icon = "inbox",
  children,
  action,
}: {
  icon?: IconName;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Icon name={icon} size={28} />
      <p>{children}</p>
      {action}
    </div>
  );
}
