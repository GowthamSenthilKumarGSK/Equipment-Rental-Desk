import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icon";

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** A link back to the list this page belongs to. */
  back?: { to: string; label: string };
  /** Status badges or other short facts shown beside the title. */
  meta?: ReactNode;
  /** Primary page actions, aligned to the right on wide screens. */
  actions?: ReactNode;
  /** A leading element such as an avatar. */
  lead?: ReactNode;
}

/** Every page opens with the same header, so the title, its context and its actions sit in one place. */
export function PageHeader({ title, description, back, meta, actions, lead }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__text">
        {back && (
          <Link to={back.to} className="page-header__back">
            <Icon name="back" size={16} />
            {back.label}
          </Link>
        )}
        <div className="page-header__title">
          {lead}
          <h1>{title}</h1>
          {meta}
        </div>
        {description && <p className="page-header__desc">{description}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}
