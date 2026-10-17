import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, toApiError, type ApiError } from "../api";
import type { Member } from "../types";
import { TextField } from "./Field";
import { ErrorNotice, Notice } from "./Notice";

type Outcome = { kind: "created"; member: Member } | { kind: "failed"; error: ApiError } | null;

// The same shape the API accepts: digits, optional leading +, spaces, dashes, brackets.
const PHONE_SHAPE = /^\+?[0-9][0-9 ()-]{4,19}$/;

export function AddMemberForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problems: Record<string, string> = {};
    if (!name.trim()) problems.name = "Enter the member's name.";
    if (!PHONE_SHAPE.test(phone.trim())) {
      problems.phone = "Enter a phone number with 5 to 20 digits, spaces or dashes.";
    }
    setErrors(problems);
    if (Object.keys(problems).length > 0) return;
    setBusy(true);
    try {
      const member = await api.createMember({ name: name.trim(), phone: phone.trim() });
      setOutcome({ kind: "created", member });
      setName("");
      setPhone("");
      onCreated();
    } catch (error) {
      setOutcome({ kind: "failed", error: toApiError(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="panel">
      <summary>Register a member</summary>
      <form onSubmit={submit} noValidate className="form" aria-label="Register a member">
        <TextField
          label="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={errors.name}
          maxLength={100}
          required
        />
        <TextField
          label="Phone"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          error={errors.phone}
          hint="For example +91 98765 43210"
          inputMode="tel"
          maxLength={20}
          required
        />
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Registering…" : "Register member"}
        </button>
        {outcome?.kind === "created" && (
          <Notice kind="success">
            Registered <Link to={`/members/${outcome.member.id}`}>{outcome.member.name}</Link>.
          </Notice>
        )}
        {outcome?.kind === "failed" && <ErrorNotice error={outcome.error} />}
      </form>
    </details>
  );
}
