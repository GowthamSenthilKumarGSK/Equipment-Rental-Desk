/** The first letters of a name. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const letters =
    parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0];
  return letters.toUpperCase();
}

/** A round marker with the person's initials. Decoration only: the name is always written out beside it. */
export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  return (
    <span className={large ? "avatar avatar--lg" : "avatar"} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
