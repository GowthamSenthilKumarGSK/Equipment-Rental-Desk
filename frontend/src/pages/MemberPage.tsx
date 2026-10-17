import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, toApiError, type ApiError } from "../api";
import { parseId } from "../availability";
import { TextField } from "../components/Field";
import { ErrorNotice, Loading, Notice } from "../components/Notice";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, formatIst, formatRupees, parseRupees, pluralise } from "../format";
import { blockReasonText, loanLimitText } from "../messages";
import type { Statement, StatementLoan } from "../types";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

type Feedback = { kind: "success"; text: string } | { kind: "error"; error: ApiError } | null;

function isActive(row: StatementLoan): boolean {
  return row.status === "reserved" || row.status === "checked_out";
}

function loanTiming(row: StatementLoan): string {
  if (row.status === "reserved") return `Hold ends ${formatIst(row.loan.expires_at)}`;
  if (row.status === "checked_out") return `Due ${formatIst(row.loan.due_at)}`;
  if (row.status === "returned") return `Returned ${formatIst(row.loan.returned_at)}`;
  if (row.status === "cancelled") return `Cancelled ${formatIst(row.loan.cancelled_at)}`;
  return `Reserved ${formatIst(row.loan.reserved_at)}, hold ran out`;
}

function LoanStatusCell({ row }: { row: StatementLoan }) {
  if (row.is_overdue) {
    return (
      <>
        <StatusBadge status="late" />{" "}
        <span className="muted">{pluralise(row.days_overdue, "day")}</span>
      </>
    );
  }
  return <StatusBadge status={row.status} />;
}

function LoansTable({ rows, caption }: { rows: StatementLoan[]; caption: string }) {
  return (
    <div className="table-wrap">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col">Status</th>
            <th scope="col">When</th>
            <th scope="col" className="num">
              Late fee
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.loan.id}>
              <td>
                <Link to={`/items/${row.loan.item_id}`}>{row.item_name}</Link>
              </td>
              <td>
                <LoanStatusCell row={row} />
              </td>
              <td>{loanTiming(row)}</td>
              <td className="num">
                {row.loan.fee_charged_paise > 0 ? formatRupees(row.loan.fee_charged_paise) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BorrowingStatus({ statement }: { statement: Statement }) {
  const atLimit = statement.at_loan_limit;
  if (statement.block_reasons.length === 0) {
    return atLimit ? (
      <Notice kind="info">
        <strong>At the loan limit.</strong> {loanLimitText(statement.active_loan_count)} They can
        still check out items they have already reserved.
      </Notice>
    ) : (
      <Notice kind="info">
        <strong>Can borrow.</strong> Nothing is blocking this member from reserving or checking out.
      </Notice>
    );
  }
  return (
    <section className="blocked" aria-labelledby="blocked-heading">
      <h2 id="blocked-heading">Why this member can't borrow</h2>
      <ul>
        {statement.block_reasons.map((reason) => (
          <li key={reason}>{blockReasonText(reason)}</li>
        ))}
      </ul>
      {atLimit && <p>{loanLimitText(statement.active_loan_count)}</p>}
    </section>
  );
}

interface PaymentFormProps {
  memberId: number;
  balancePaise: number;
  onRecorded: (text: string) => void;
}

function PaymentForm({ memberId, balancePaise, onRecorded }: PaymentFormProps) {
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setFailure(null);
    const paise = parseRupees(amount);
    if (paise === null) {
      setProblem("Enter the amount in rupees, like 250 or 250.50.");
      return;
    }
    if (paise === 0) {
      setProblem("The amount must be more than zero.");
      return;
    }
    setProblem("");
    setBusy(true);
    try {
      const payment = await api.recordPayment(memberId, paise, note.trim());
      setAmount("");
      setNote("");
      onRecorded(`Recorded a payment of ${formatRupees(payment.amount_paise)}.`);
    } catch (error) {
      setFailure(toApiError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="form" aria-label="Record a payment">
      <TextField
        label="Amount (₹)"
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
        error={problem}
        hint={`Outstanding balance: ${formatRupees(balancePaise)}`}
        inputMode="decimal"
        required
      />
      <TextField
        label="Note (optional)"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        maxLength={200}
      />
      <button type="submit" className="button" disabled={busy || balancePaise === 0}>
        {busy ? "Recording…" : "Record payment"}
      </button>
      {balancePaise === 0 && <p className="hint">Nothing is owed, so there is nothing to pay.</p>}
      {failure && <ErrorNotice error={failure} />}
    </form>
  );
}

function MemberDetail({ id }: { id: number }) {
  const statement = useAsync(`member:${id}`, (signal) => api.getStatement(id, signal));
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  useTitle(statement.data?.member.name ?? "Member");

  async function run(task: () => Promise<string>) {
    setBusy(true);
    setFeedback(null);
    try {
      setFeedback({ kind: "success", text: await task() });
    } catch (error) {
      setFeedback({ kind: "error", error: toApiError(error) });
    } finally {
      setBusy(false);
      statement.reload();
    }
  }

  if (statement.error && !statement.data) {
    return (
      <>
        <h1>Member</h1>
        <ErrorNotice error={statement.error} onRetry={statement.reload} />
        <p>
          <Link to="/members">Back to all members</Link>
        </p>
      </>
    );
  }
  if (!statement.data) return <Loading what="member" />;

  const data = statement.data;
  const { member } = data;
  const active = data.loans.filter(isActive);
  const history = data.loans.filter((row) => !isActive(row));

  return (
    <>
      <p>
        <Link to="/members">← All members</Link>
      </p>
      <div className="title-row">
        <h1>{member.name}</h1>
        <StatusBadge status={member.status} />
      </div>
      <p className="muted">
        {member.phone} · joined {formatDate(member.join_date)}
      </p>

      {feedback?.kind === "success" && <Notice kind="success">{feedback.text}</Notice>}
      {feedback?.kind === "error" && <ErrorNotice error={feedback.error} />}

      <BorrowingStatus statement={data} />

      <dl className="facts">
        <dt>Fee balance</dt>
        <dd>
          <strong>{formatRupees(data.balance_paise)}</strong>
        </dd>
        <dt>Fees charged so far</dt>
        <dd>{formatRupees(data.total_fees_paise)}</dd>
        <dt>Paid so far</dt>
        <dd>{formatRupees(data.total_payments_paise)}</dd>
        <dt>Active loans</dt>
        <dd>{data.active_loan_count}</dd>
      </dl>

      <section aria-labelledby="active-heading">
        <h2 id="active-heading">Active loans</h2>
        {active.length === 0 ? (
          <p className="muted">No active loans.</p>
        ) : (
          <LoansTable rows={active} caption="Reserved and checked-out items" />
        )}
      </section>

      <section aria-labelledby="history-heading">
        <h2 id="history-heading">Loan history</h2>
        {history.length === 0 ? (
          <p className="muted">No past loans.</p>
        ) : (
          <LoansTable rows={history} caption="Returned, cancelled and expired loans" />
        )}
      </section>

      <section aria-labelledby="payments-heading">
        <h2 id="payments-heading">Payments</h2>
        {data.payments.length === 0 ? (
          <p className="muted">No payments yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <caption>Payments received</caption>
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Note</th>
                  <th scope="col" className="num">
                    Amount
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.payments.map((payment) => (
                  <tr key={payment.id}>
                    <td>{formatIst(payment.paid_at)}</td>
                    <td>{payment.note ?? "—"}</td>
                    <td className="num">{formatRupees(payment.amount_paise)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <PaymentForm
          memberId={id}
          balancePaise={data.balance_paise}
          onRecorded={(text) => {
            setFeedback({ kind: "success", text });
            statement.reload();
          }}
        />
      </section>

      <section aria-labelledby="suspension-heading">
        <h2 id="suspension-heading">Suspension</h2>
        {member.status === "suspended" ? (
          <div className="action">
            <p>This member is suspended and cannot reserve or check out. Their history is kept.</p>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await api.reinstateMember(id);
                  return `${member.name} is active again.`;
                })
              }
            >
              Lift suspension
            </button>
          </div>
        ) : (
          <form
            className="form"
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await api.suspendMember(id, reason.trim());
                setReason("");
                return `${member.name} is now suspended.`;
              });
            }}
          >
            <TextField
              label="Reason (optional)"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={200}
            />
            <button type="submit" className="button button--danger" disabled={busy}>
              Suspend member
            </button>
          </form>
        )}
      </section>
    </>
  );
}

export default function MemberPage() {
  const { memberId } = useParams();
  const id = parseId(memberId);
  useTitle("Member");
  if (id === null) {
    return (
      <>
        <h1>Member not found</h1>
        <Notice kind="error">“{memberId}” is not a valid member number.</Notice>
        <p>
          <Link to="/members">Back to all members</Link>
        </p>
      </>
    );
  }
  return <MemberDetail key={id} id={id} />;
}
