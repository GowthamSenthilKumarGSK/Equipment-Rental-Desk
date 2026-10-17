import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { AddItemForm } from "../components/AddItemForm";
import { SelectField, TextField } from "../components/Field";
import { ErrorNotice, Loading } from "../components/Notice";
import { Pager, PastTheEnd } from "../components/Pager";
import { StatusBadge } from "../components/StatusBadge";
import { availabilityText } from "../availability";
import { formatRupees } from "../format";
import { ITEM_STATUS_LABELS } from "../messages";
import { isPastEnd } from "../paging";
import type { ItemStatus } from "../types";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

const PAGE_SIZE = 12;
const STATUSES = Object.keys(ITEM_STATUS_LABELS) as ItemStatus[];

function SearchBox({ initial, onSearch }: { initial: string; onSearch: (text: string) => void }) {
  const [text, setText] = useState(initial);
  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch(text.trim());
  }
  return (
    <form onSubmit={submit} role="search" className="search">
      <TextField
        label="Search by name"
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

export default function ItemsPage() {
  useTitle("Items");
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const status = (params.get("status") ?? "") as ItemStatus | "";
  const offset = (Math.max(1, Number(params.get("page")) || 1) - 1) * PAGE_SIZE;

  function change(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page"); // a new filter starts again from page 1
    setParams(next);
  }

  const items = useAsync(`items:${q}|${category}|${status}|${offset}`, (signal) =>
    api.listItems({ q, category, status, limit: PAGE_SIZE, offset }, signal),
  );
  const categories = useAsync("categories", (signal) =>
    api
      .listItems({ limit: 200 }, signal)
      .then((page) => [...new Set(page.results.map((item) => item.category))].sort()),
  );
  const filtered = Boolean(q || category || status);
  const pastEnd = items.data ? isPastEnd(items.data.total, offset) : false;

  return (
    <>
      <h1>Items</h1>
      <div className="toolbar" role="group" aria-label="Filter items">
        <SearchBox key={q} initial={q} onSearch={(text) => change({ q: text })} />
        <SelectField
          label="Category"
          value={category}
          onChange={(event) => change({ category: event.target.value })}
        >
          <option value="">All categories</option>
          {(categories.data ?? []).map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </SelectField>
        <SelectField
          label="Status"
          value={status}
          onChange={(event) => change({ status: event.target.value })}
        >
          <option value="">Any status</option>
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {ITEM_STATUS_LABELS[value]}
            </option>
          ))}
        </SelectField>
      </div>

      {items.error && <ErrorNotice error={items.error} onRetry={items.reload} />}
      {items.loading && !items.data && <Loading what="items" />}
      {pastEnd && items.data && (
        <PastTheEnd
          total={items.data.total}
          limit={PAGE_SIZE}
          what="item"
          onOffsetChange={(next) => change({ page: String(next / PAGE_SIZE + 1) })}
        />
      )}
      {items.data && items.data.results.length === 0 && !pastEnd && (
        <div className="empty">
          <p>{filtered ? "No items match these filters." : "There are no items yet."}</p>
          {filtered && (
            <Link to="/items" className="button button--secondary">
              Clear filters
            </Link>
          )}
        </div>
      )}
      {items.data && items.data.results.length > 0 && (
        <ul className="cards" aria-label="Items">
          {items.data.results.map((item) => (
            <li key={item.id} className="card">
              <div className="card__main">
                <h2>
                  <Link to={`/items/${item.id}`}>{item.name}</Link>
                </h2>
                <p className="muted">
                  {item.category} · replacement value {formatRupees(item.replacement_value_paise)}
                </p>
                <p>{availabilityText(item)}</p>
              </div>
              <StatusBadge status={item.status} />
            </li>
          ))}
        </ul>
      )}
      {items.data && (
        <Pager
          noun="Item"
          total={items.data.total}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={(next) => change({ page: String(next / PAGE_SIZE + 1) })}
        />
      )}

      <AddItemForm
        categories={categories.data ?? []}
        onCreated={() => {
          items.reload();
          categories.reload();
        }}
      />
    </>
  );
}
