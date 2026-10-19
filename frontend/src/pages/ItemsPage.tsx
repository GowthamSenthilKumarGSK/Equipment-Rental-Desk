import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { AddItemForm } from "../components/AddItemForm";
import { SelectField, TextField } from "../components/Field";
import { EmptyState } from "../components/EmptyState";
import { Icon } from "../components/Icon";
import { Stat, Stats, type Tone } from "../components/Kpis";
import { ErrorNotice, Loading } from "../components/Notice";
import { PageHeader } from "../components/PageHeader";
import { SkeletonCards } from "../components/Skeleton";
import { Pager, PastTheEnd } from "../components/Pager";
import { StatusBadge } from "../components/StatusBadge";
import { availabilityText } from "../availability";
import { formatRupees } from "../format";
import { ITEM_STATUS_LABELS } from "../messages";
import { isPastEnd } from "../paging";
import type { ItemStatus } from "../types";
import { useAsync, type AsyncState } from "../useAsync";
import { useTitle } from "../useTitle";

const PAGE_SIZE = 12;
const STATUSES = Object.keys(ITEM_STATUS_LABELS) as ItemStatus[];

const STATUS_TONES: Record<ItemStatus, Tone> = {
  available: "ok",
  reserved: "info",
  checked_out: "warn",
  overdue: "danger",
  under_maintenance: "orange",
};

type Counts = { total: number; byStatus: Record<ItemStatus, number> };
interface Inventory {
  categories: string[];
  /** Null when the counts could not be worked out; the list below still works. */
  counts: Counts | null;
}

/** One request per status, each asking for a single record and reading its `total`. */
function loadCountsByStatus(signal: AbortSignal): Promise<Counts> {
  return Promise.all([
    api.listItems({ limit: 1 }, signal),
    ...STATUSES.map((status) => api.listItems({ status, limit: 1 }, signal)),
  ]).then(([all, ...byStatus]) => ({
    total: all.total,
    byStatus: Object.fromEntries(
      STATUSES.map((status, i) => [status, byStatus[i].total]),
    ) as Record<ItemStatus, number>,
  }));
}

/**
 * The category choices and the inventory counts come from one request for up to 200 items. When
 * that request holds every item, the counts are simply tallied from it. Only for a larger
 * inventory does the page fall back to asking the API for each status's total.
 */
async function loadInventory(signal: AbortSignal): Promise<Inventory> {
  const everything = await api.listItems({ limit: 200 }, signal);
  const categories = [...new Set(everything.results.map((item) => item.category))].sort();
  if (everything.results.length >= everything.total) {
    const byStatus = Object.fromEntries(STATUSES.map((status) => [status, 0])) as Record<
      ItemStatus,
      number
    >;
    for (const item of everything.results) byStatus[item.status] += 1;
    return { categories, counts: { total: everything.total, byStatus } };
  }
  return { categories, counts: await loadCountsByStatus(signal).catch(() => null) };
}

function InventorySummary({ state }: { state: AsyncState<Inventory> }) {
  if (state.loading && !state.data) return <SkeletonCards count={6} />;
  const counts = state.data?.counts;
  if (!counts) {
    return (
      <p className="hint">
        The inventory summary is not available right now.{" "}
        <button type="button" className="link-button" onClick={state.reload}>
          Retry the summary
        </button>
      </p>
    );
  }
  const { total, byStatus } = counts;
  return (
    <Stats label="Inventory summary" compact>
      <Stat label="All items" value={String(total)} to="/items" />
      {STATUSES.map((status) => (
        <Stat
          key={status}
          label={ITEM_STATUS_LABELS[status]}
          value={String(byStatus[status])}
          tone={STATUS_TONES[status]}
          to={`/items?status=${status}`}
        />
      ))}
    </Stats>
  );
}

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
  const inventory = useAsync("inventory", loadInventory);
  const filtered = Boolean(q || category || status);
  const pastEnd = items.data ? isPastEnd(items.data.total, offset) : false;

  return (
    <>
      <PageHeader
        title="Items"
        description="Every item on the shelf: what is free to lend, what is out and when it is due back."
      />
      <InventorySummary state={inventory} />
      <AddItemForm
        categories={inventory.data?.categories ?? []}
        onCreated={() => {
          items.reload();
          inventory.reload();
        }}
      />
      <div className="toolbar" role="group" aria-label="Filter items">
        <SearchBox key={q} initial={q} onSearch={(text) => change({ q: text })} />
        <SelectField
          label="Category"
          value={category}
          onChange={(event) => change({ category: event.target.value })}
        >
          <option value="">All categories</option>
          {(inventory.data?.categories ?? []).map((name) => (
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
      {items.loading && !items.data && <Loading what="items" shape="list" />}
      {pastEnd && items.data && (
        <PastTheEnd
          total={items.data.total}
          limit={PAGE_SIZE}
          what="item"
          onOffsetChange={(next) => change({ page: String(next / PAGE_SIZE + 1) })}
        />
      )}
      {items.data && items.data.results.length === 0 && !pastEnd && (
        <EmptyState
          icon="search"
          action={
            filtered && (
              <Link to="/items" className="button button--secondary">
                Clear filters
              </Link>
            )
          }
        >
          {filtered ? "No items match these filters." : "There are no items yet."}
        </EmptyState>
      )}
      {items.data && items.data.results.length > 0 && (
        <>
          <div className="list-head" aria-hidden="true">
            <span>Item</span>
            <span>Availability</span>
            <span>Status</span>
          </div>
          <ul className="cards" aria-label="Items">
            {items.data.results.map((item) => (
              <li key={item.id} className="row row--item">
                <div className="row__main">
                  <h2>
                    <Link to={`/items/${item.id}`}>{item.name}</Link>
                  </h2>
                  <p className="muted">
                    {item.category} · replacement value {formatRupees(item.replacement_value_paise)}
                  </p>
                </div>
                <p className="row__avail">
                  <Icon name="calendar" size={14} /> {availabilityText(item)}
                </p>
                <div className="row__badge">
                  <StatusBadge status={item.status} />
                </div>
              </li>
            ))}
          </ul>
        </>
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
    </>
  );
}
