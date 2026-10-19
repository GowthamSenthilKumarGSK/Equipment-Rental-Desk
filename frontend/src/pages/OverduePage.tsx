import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState } from "../components/EmptyState";
import { Stat, Stats } from "../components/Kpis";
import { ErrorNotice, Loading } from "../components/Notice";
import { PageHeader } from "../components/PageHeader";
import { Pager, PastTheEnd } from "../components/Pager";
import { TableWrap } from "../components/TableWrap";
import { formatIst, formatRupees, pluralise } from "../format";
import { isPastEnd } from "../paging";
import { severityOf } from "../severity";
import type { OverdueLoan } from "../types";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

const PAGE_SIZE = 20;

/** Figures that are exact for the data on screen; the labels say so when only one page is loaded. */
function OverdueSummary({
  rows,
  total,
  offset,
}: {
  rows: OverdueLoan[];
  total: number;
  offset: number;
}) {
  const feesPaise = rows.reduce((sum, row) => sum + row.fee_if_returned_now_paise, 0);
  const allOnScreen = rows.length === total;
  return (
    <Stats label="Overdue summary">
      <Stat label="Overdue loans" value={String(total)} icon="clock" tone="danger" />
      {offset === 0 && rows.length > 0 && (
        <Stat
          label="Longest overdue"
          value={pluralise(rows[0].days_overdue, "day")}
          icon="warning"
          tone="orange"
          note={`${rows[0].item_name}, ${rows[0].member_name}`}
        />
      )}
      <Stat
        label="Fees if returned now"
        value={formatRupees(feesPaise)}
        icon="rupee"
        note={allOnScreen ? "All overdue loans" : "Only the loans on this page"}
      />
    </Stats>
  );
}

export default function OverduePage() {
  useTitle("Overdue");
  const [offset, setOffset] = useState(0);
  const overdue = useAsync(`overdue:${offset}`, (signal) =>
    api.listOverdue({ limit: PAGE_SIZE, offset }, signal),
  );

  const pastEnd = overdue.data ? isPastEnd(overdue.data.total, offset) : false;

  return (
    <>
      <PageHeader
        title="Overdue loans"
        description="Longest overdue first. Open an item to return it."
      />

      {overdue.error && <ErrorNotice error={overdue.error} onRetry={overdue.reload} />}
      {overdue.loading && !overdue.data && <Loading what="overdue loans" shape="list" />}
      {pastEnd && overdue.data && (
        <PastTheEnd
          total={overdue.data.total}
          limit={PAGE_SIZE}
          what="overdue loan"
          onOffsetChange={setOffset}
        />
      )}
      {overdue.data && overdue.data.results.length === 0 && !pastEnd && (
        <EmptyState icon="check">Nothing is overdue.</EmptyState>
      )}
      {overdue.data && overdue.data.results.length > 0 && (
        <>
          <OverdueSummary rows={overdue.data.results} total={overdue.data.total} offset={offset} />
          <TableWrap label="Overdue loans table">
            {/* Explicit roles keep the table a table for assistive technology when the narrow-screen
                styles turn each row into a card. */}
            <table className="table--stack" role="table">
              <caption>Loans past their due time</caption>
              <thead role="rowgroup">
                <tr role="row">
                  <th scope="col" role="columnheader">
                    Item
                  </th>
                  <th scope="col" role="columnheader">
                    Member
                  </th>
                  <th scope="col" role="columnheader">
                    Was due
                  </th>
                  <th scope="col" role="columnheader" className="num">
                    Days overdue
                  </th>
                  <th scope="col" role="columnheader" className="num">
                    Fee if returned now
                  </th>
                  <th scope="col" role="columnheader">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {overdue.data.results.map((row) => {
                  const severity = severityOf(row.days_overdue);
                  return (
                    <tr key={row.loan_id} role="row" className={severity.rowClass || undefined}>
                      <td role="cell" data-label="Item">
                        <Link to={`/items/${row.item_id}`}>{row.item_name}</Link>
                      </td>
                      <td role="cell" data-label="Member">
                        <span className="cell">
                          <Link to={`/members/${row.member_id}`}>{row.member_name}</Link>
                          <br />
                          <span className="muted">{row.member_phone}</span>
                        </span>
                      </td>
                      <td role="cell" data-label="Was due">
                        <span className="cell">{formatIst(row.due_at)}</span>
                      </td>
                      <td role="cell" className="num" data-label="Days overdue">
                        <span className="cell">
                          {pluralise(row.days_overdue, "day")}
                          <br />
                          <span className={`sev sev--${severity.level}`}>{severity.label}</span>
                        </span>
                      </td>
                      <td role="cell" className="num" data-label="Fee if returned now">
                        <span className="cell">{formatRupees(row.fee_if_returned_now_paise)}</span>
                      </td>
                      <td role="cell" data-label="Action">
                        <Link
                          to={`/items/${row.item_id}`}
                          className="button button--small button--secondary"
                        >
                          Open to return
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
        </>
      )}
      {overdue.data && (
        <Pager
          noun="Overdue loan"
          total={overdue.data.total}
          limit={PAGE_SIZE}
          offset={offset}
          onOffsetChange={setOffset}
        />
      )}
    </>
  );
}
