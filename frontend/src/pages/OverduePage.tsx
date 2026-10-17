import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorNotice, Loading } from "../components/Notice";
import { Pager, PastTheEnd } from "../components/Pager";
import { formatIst, formatRupees, pluralise } from "../format";
import { isPastEnd } from "../paging";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

const PAGE_SIZE = 20;

export default function OverduePage() {
  useTitle("Overdue");
  const [offset, setOffset] = useState(0);
  const overdue = useAsync(`overdue:${offset}`, (signal) =>
    api.listOverdue({ limit: PAGE_SIZE, offset }, signal),
  );

  const pastEnd = overdue.data ? isPastEnd(overdue.data.total, offset) : false;

  return (
    <>
      <h1>Overdue loans</h1>
      <p className="muted">Longest overdue first. Open an item to return it.</p>

      {overdue.error && <ErrorNotice error={overdue.error} onRetry={overdue.reload} />}
      {overdue.loading && !overdue.data && <Loading what="overdue loans" />}
      {pastEnd && overdue.data && (
        <PastTheEnd
          total={overdue.data.total}
          limit={PAGE_SIZE}
          what="overdue loan"
          onOffsetChange={setOffset}
        />
      )}
      {overdue.data && overdue.data.results.length === 0 && !pastEnd && (
        <div className="empty">
          <p>Nothing is overdue.</p>
        </div>
      )}
      {overdue.data && overdue.data.results.length > 0 && (
        <div className="table-wrap">
          <table>
            <caption>Loans past their due time</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Member</th>
                <th scope="col">Was due</th>
                <th scope="col" className="num">
                  Days overdue
                </th>
                <th scope="col" className="num">
                  Fee if returned now
                </th>
              </tr>
            </thead>
            <tbody>
              {overdue.data.results.map((row) => (
                <tr key={row.loan_id}>
                  <td>
                    <Link to={`/items/${row.item_id}`}>{row.item_name}</Link>
                  </td>
                  <td>
                    <Link to={`/members/${row.member_id}`}>{row.member_name}</Link>
                    <br />
                    <span className="muted">{row.member_phone}</span>
                  </td>
                  <td>{formatIst(row.due_at)}</td>
                  <td className="num">{pluralise(row.days_overdue, "day")}</td>
                  <td className="num">{formatRupees(row.fee_if_returned_now_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
