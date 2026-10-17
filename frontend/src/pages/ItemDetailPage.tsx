import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, toApiError, type ApiError } from "../api";
import { availabilityText, parseId } from "../availability";
import { ErrorNotice, Loading, Notice } from "../components/Notice";
import { MemberPicker } from "../components/MemberPicker";
import { StatusBadge } from "../components/StatusBadge";
import { formatIst, formatRupees } from "../format";
import { ACTION_LABELS, LOAN_STATUS_LABELS } from "../messages";
import type { Item, Member } from "../types";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

type Feedback = { kind: "success"; text: string } | { kind: "error"; error: ApiError } | null;

interface ActionButtonProps {
  label: string;
  help: string;
  busy: boolean;
  onClick: () => void;
}

function ActionButton({ label, help, busy, onClick }: ActionButtonProps) {
  return (
    <div className="action">
      <button type="button" className="button" disabled={busy} onClick={onClick}>
        {label}
      </button>
      <p className="hint">{help}</p>
    </div>
  );
}

function CurrentLoan({ item }: { item: Item }) {
  const loan = item.current_loan;
  if (!loan) return null;
  return (
    <section aria-labelledby="loan-heading">
      <h2 id="loan-heading">Current loan</h2>
      <dl className="facts">
        <dt>Member</dt>
        <dd>
          <Link to={`/members/${loan.member_id}`}>Member #{loan.member_id}</Link>
        </dd>
        <dt>Loan status</dt>
        <dd>{LOAN_STATUS_LABELS[loan.status]}</dd>
        <dt>Reserved</dt>
        <dd>{formatIst(loan.reserved_at)}</dd>
        {loan.status === "reserved" && (
          <>
            <dt>Hold ends</dt>
            <dd>{formatIst(loan.expires_at)}</dd>
          </>
        )}
        {loan.status === "checked_out" && (
          <>
            <dt>Checked out</dt>
            <dd>{formatIst(loan.checked_out_at)}</dd>
            <dt>Due back</dt>
            <dd>{formatIst(loan.due_at)}</dd>
          </>
        )}
      </dl>
    </section>
  );
}

function ItemDetail({ id }: { id: number }) {
  const item = useAsync(`item:${id}`, (signal) => api.getItem(id, signal));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [member, setMember] = useState<Member | null>(null);
  useTitle(item.data?.name ?? "Item");

  /** Runs one action. Whatever happens, the item is fetched again so the page shows the truth. */
  async function run(task: () => Promise<string>) {
    setBusy(true);
    setFeedback(null);
    try {
      setFeedback({ kind: "success", text: await task() });
    } catch (error) {
      setFeedback({ kind: "error", error: toApiError(error) });
    } finally {
      setBusy(false);
      item.reload();
    }
  }

  if (item.error && !item.data) {
    return (
      <>
        <h1>Item</h1>
        <ErrorNotice error={item.error} onRetry={item.reload} />
        <p>
          <Link to="/items">Back to all items</Link>
        </p>
      </>
    );
  }
  if (!item.data) return <Loading what="item" />;

  const current = item.data;
  const can = (action: Item["allowed_actions"][number]) => current.allowed_actions.includes(action);

  return (
    <>
      <p>
        <Link to="/items">← All items</Link>
      </p>
      <div className="title-row">
        <h1>{current.name}</h1>
        <StatusBadge status={current.status} />
      </div>
      <p>{availabilityText(current)}</p>

      <dl className="facts">
        <dt>Category</dt>
        <dd>{current.category}</dd>
        <dt>Replacement value</dt>
        <dd>{formatRupees(current.replacement_value_paise)}</dd>
        <dt>Condition</dt>
        <dd>{current.condition_note || "No note"}</dd>
      </dl>

      <CurrentLoan item={current} />

      <section aria-labelledby="actions-heading">
        <h2 id="actions-heading">Actions</h2>
        {feedback?.kind === "success" && <Notice kind="success">{feedback.text}</Notice>}
        {feedback?.kind === "error" && <ErrorNotice error={feedback.error} />}
        {current.allowed_actions.length === 0 && (
          <p className="muted">Nothing can be done with this item right now.</p>
        )}

        {can("reserve") && (
          <div className="action">
            <h3>{ACTION_LABELS.reserve}</h3>
            <MemberPicker selected={member} onSelect={setMember} />
            <button
              type="button"
              className="button"
              disabled={busy || member === null}
              onClick={() =>
                member &&
                run(async () => {
                  const loan = await api.reserveItem(id, member.id);
                  setMember(null);
                  return `Reserved for ${member.name}. The hold lasts until ${formatIst(loan.expires_at)}.`;
                })
              }
            >
              {member ? `Reserve for ${member.name}` : "Choose a member to reserve for"}
            </button>
            <p className="hint">Holds the item for the member until the hold runs out.</p>
          </div>
        )}
        {can("check_out") && (
          <ActionButton
            label={ACTION_LABELS.check_out}
            help="Hands the item to the member who reserved it."
            busy={busy}
            onClick={() =>
              run(async () => {
                const loan = await api.checkOut(id);
                return `Checked out. It is due back ${formatIst(loan.due_at)}.`;
              })
            }
          />
        )}
        {can("return") && (
          <ActionButton
            label={ACTION_LABELS.return}
            help="Takes the item back. Any late fee is added to the member's balance."
            busy={busy}
            onClick={() =>
              run(async () => {
                const loan = await api.returnItem(id);
                return loan.fee_charged_paise > 0
                  ? `Returned. A late fee of ${formatRupees(loan.fee_charged_paise)} was added to the member's balance.`
                  : "Returned on time. No late fee.";
              })
            }
          />
        )}
        {can("cancel_reservation") && (
          <ActionButton
            label={ACTION_LABELS.cancel_reservation}
            help="Releases the hold so someone else can reserve the item."
            busy={busy}
            onClick={() =>
              run(async () => {
                await api.cancelReservation(id);
                return "Reservation cancelled.";
              })
            }
          />
        )}
        {can("start_maintenance") && (
          <ActionButton
            label={ACTION_LABELS.start_maintenance}
            help="Takes the item out of use (staff)."
            busy={busy}
            onClick={() =>
              run(async () => {
                await api.startMaintenance(id);
                return "The item is now under maintenance.";
              })
            }
          />
        )}
        {can("finish_maintenance") && (
          <ActionButton
            label={ACTION_LABELS.finish_maintenance}
            help="Puts the item back into circulation (staff)."
            busy={busy}
            onClick={() =>
              run(async () => {
                await api.finishMaintenance(id);
                return "The item is available again.";
              })
            }
          />
        )}
      </section>
    </>
  );
}

export default function ItemDetailPage() {
  const { itemId } = useParams();
  const id = parseId(itemId);
  useTitle("Item");
  if (id === null) {
    return (
      <>
        <h1>Item not found</h1>
        <Notice kind="error">“{itemId}” is not a valid item number.</Notice>
        <p>
          <Link to="/items">Back to all items</Link>
        </p>
      </>
    );
  }
  return <ItemDetail key={id} id={id} />;
}
