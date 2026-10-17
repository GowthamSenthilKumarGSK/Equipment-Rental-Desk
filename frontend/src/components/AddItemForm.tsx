import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, toApiError, type ApiError } from "../api";
import { parseRupees } from "../format";
import type { Item } from "../types";
import { TextField } from "./Field";
import { ErrorNotice, Notice } from "./Notice";

type Outcome = { kind: "created"; item: Item } | { kind: "failed"; error: ApiError } | null;

interface AddItemFormProps {
  categories: string[];
  onCreated: () => void;
}

export function AddItemForm({ categories, onCreated }: AddItemFormProps) {
  const listId = useId();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [value, setValue] = useState("");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(null);

  function validate(): { problems: Record<string, string>; paise: number | null } {
    const problems: Record<string, string> = {};
    if (!name.trim()) problems.name = "Enter the item's name.";
    if (!category.trim()) problems.category = "Enter a category, such as Power Tools.";
    const paise = parseRupees(value);
    if (paise === null) problems.value = "Enter the value in rupees, like 1500 or 1500.50.";
    else if (paise === 0) problems.value = "The value must be more than zero.";
    return { problems, paise };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const { problems, paise } = validate();
    setErrors(problems);
    if (Object.keys(problems).length > 0 || paise === null) return;
    setBusy(true);
    try {
      const item = await api.createItem({
        name: name.trim(),
        category: category.trim(),
        replacement_value_paise: paise,
        condition_note: note.trim(),
      });
      setOutcome({ kind: "created", item });
      setName("");
      setValue("");
      setNote("");
      onCreated();
    } catch (error) {
      setOutcome({ kind: "failed", error: toApiError(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="panel">
      <summary>Add an item</summary>
      <form onSubmit={submit} noValidate className="form" aria-label="Add an item">
        <TextField
          label="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={errors.name}
          maxLength={100}
          required
        />
        <TextField
          label="Category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          error={errors.category}
          maxLength={50}
          list={listId}
          required
        />
        <datalist id={listId}>
          {categories.map((existing) => (
            <option key={existing} value={existing} />
          ))}
        </datalist>
        <TextField
          label="Replacement value (₹)"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          error={errors.value}
          hint="Late fees are never more than this."
          inputMode="decimal"
          required
        />
        <TextField
          label="Condition note (optional)"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={1000}
        />
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Adding…" : "Add item"}
        </button>
        {outcome?.kind === "created" && (
          <Notice kind="success">
            Added <Link to={`/items/${outcome.item.id}`}>{outcome.item.name}</Link>.
          </Notice>
        )}
        {outcome?.kind === "failed" && <ErrorNotice error={outcome.error} />}
      </form>
    </details>
  );
}
