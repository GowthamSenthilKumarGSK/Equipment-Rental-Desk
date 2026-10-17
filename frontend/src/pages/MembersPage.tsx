import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { AddMemberForm } from "../components/AddMemberForm";
import { SelectField, TextField } from "../components/Field";
import { ErrorNotice, Loading } from "../components/Notice";
import { Pager, PastTheEnd } from "../components/Pager";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate } from "../format";
import { isPastEnd } from "../paging";
import type { MemberStatus } from "../types";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

const PAGE_SIZE = 12;

function SearchBox({ initial, onSearch }: { initial: string; onSearch: (text: string) => void }) {
  const [text, setText] = useState(initial);
  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch(text.trim());
  }
  return (
    <form onSubmit={submit} role="search" className="search">
      <TextField
        label="Search by name or phone"
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={100}
      />
      <button type="submit" className="button">
        Search
      </button>
    </form>
  );
}

export default function MembersPage() {
  useTitle("Members");
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const status = (params.get("status") ?? "") as MemberStatus | "";
  const offset = (Math.max(1, Number(params.get("page")) || 1) - 1) * PAGE_SIZE;

  function change(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  }

  const members = useAsync(`members:${q}|${status}|${offset}`, (signal) =>
    api.listMembers({ q, status, limit: PAGE_SIZE, offset }, signal),
  );
  const filtered = Boolean(q || status);
  const pastEnd = members.data ? isPastEnd(members.data.total, offset) : false;

  return (
    <>
      <h1>Members</h1>
      <div className="toolbar" role="group" aria-label="Filter members">
        <SearchBox key={q} initial={q} onSearch={(text) => change({ q: text })} />
        <SelectField
          label="Status"
          value={status}
          onChange={(event) => change({ status: event.target.value })}
        >
          <option value="">Any status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </SelectField>
      </div>

      {members.error && <ErrorNotice error={members.error} onRetry={members.reload} />}
      {members.loading && !members.data && <Loading what="members" />}
      {pastEnd && members.data && (
        <PastTheEnd
          total={members.data.total}
          limit={PAGE_SIZE}
          what="member"
          onOffsetChange={(next) => change({ page: String(next / PAGE_SIZE + 1) })}
        />
      )}
      {members.data && members.data.results.length === 0 && !pastEnd && (
        <div className="empty">
          <p>{filtered ? "No members match these filters." : "There are no members yet."}</p>
          {filtered && (
            <Link to="/members" className="button button--secondary">
              Clear filters
            </Link>
          )}
        </div>
      )}
      {members.data && members.data.results.length > 0 && (
        <ul className="cards" aria-label="Members">
          {members.data.results.map((member) => (
            <li key={member.id} className="card">
              <div className="card__main">
                <h2>
                  <Link to={`/members/${member.id}`}>{member.name}</Link>
                </h2>
                <p className="muted">
                  {member.phone} · joined {formatDate(member.join_date)}
                </p>
              </div>
              <StatusBadge status={member.status} />
            </li>
          ))}
        </ul>
      )}
      {members.data && (
        <Pager
          noun="Member"
          total={members.data.total}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={(next) => change({ page: String(next / PAGE_SIZE + 1) })}
        />
      )}

      <AddMemberForm onCreated={members.reload} />
    </>
  );
}
