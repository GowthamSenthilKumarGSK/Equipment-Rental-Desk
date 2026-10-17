import { useEffect, useState } from "react";
import { api } from "../api";
import type { Member } from "../types";
import { useAsync } from "../useAsync";
import { ErrorNotice } from "./Notice";
import { StatusBadge } from "./StatusBadge";
import { TextField } from "./Field";

function useDebounced(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

interface MemberPickerProps {
  selected: Member | null;
  onSelect: (member: Member | null) => void;
}

/** Search members by name or phone and choose one. Suspension is shown, but the server decides. */
export function MemberPicker({ selected, onSelect }: MemberPickerProps) {
  const [text, setText] = useState("");
  const query = useDebounced(text.trim(), 250);
  const members = useAsync(`picker:${query}`, (signal) =>
    api.listMembers({ q: query, limit: 8 }, signal),
  );

  return (
    <div className="picker">
      <TextField
        label="Find a member (name or phone)"
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={100}
      />
      {members.error && <ErrorNotice error={members.error} onRetry={members.reload} />}
      {members.loading && !members.data && (
        <p className="muted" role="status">
          Searching…
        </p>
      )}
      {members.data && members.data.results.length === 0 && (
        <p className="muted">No members match “{query}”.</p>
      )}
      {members.data && members.data.results.length > 0 && (
        <fieldset className="picker__results">
          <legend>Choose a member</legend>
          {members.data.results.map((member) => (
            <label key={member.id} className="picker__option">
              <input
                type="radio"
                name="member"
                checked={selected?.id === member.id}
                onChange={() => onSelect(member)}
              />
              <span>
                {member.name} <span className="muted">· {member.phone}</span>
              </span>
              {member.status === "suspended" && <StatusBadge status="suspended" />}
            </label>
          ))}
          {members.data.total > members.data.results.length && (
            <p className="hint">
              Showing the first {members.data.results.length} of {members.data.total}. Type more of
              the name to narrow the list.
            </p>
          )}
        </fieldset>
      )}
    </div>
  );
}
