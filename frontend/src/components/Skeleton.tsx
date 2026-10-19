/**
 * Placeholder shapes shown while data loads. They are decoration (hidden from assistive
 * technology); the visible-to-screen-readers message is the "Loading …" status that wraps them.
 */
export function Skeleton({ variant }: { variant: "line" | "row" | "card" }) {
  return <span className={`skeleton skeleton--${variant}`} aria-hidden="true" />;
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-block" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} variant="row" />
      ))}
    </div>
  );
}

export function SkeletonCards({ count = 4 }: { count?: number }) {
  return (
    <div className="skeleton-cards" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <Skeleton key={index} variant="card" />
      ))}
    </div>
  );
}

export function SkeletonLines({ lines = 4 }: { lines?: number }) {
  return (
    <div className="skeleton-block" aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} variant="line" />
      ))}
    </div>
  );
}
