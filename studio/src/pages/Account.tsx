import { useState } from "react";
import { changePassword } from "../api";
import { Field } from "./Login";

export default function Account() {
  const [old, setOld] = useState("");
  const [next, setNext] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await changePassword(old, next);
      setNote("Your password is changed. Other browsers are signed out.");
      setOld("");
      setNext("");
    } catch (err) {
      setNote((err as Error).message);
    }
  };
  return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="text-xl font-semibold">Your account</h1>
      {note && <p className="mt-3 rounded bg-amber-50 p-2 text-sm" role="status">{note}</p>}
      <form onSubmit={submit} className="mt-4 grid gap-3">
        <Field label="Current password" type="password" value={old} onChange={setOld} />
        <Field label="New password" type="password" value={next} onChange={setNext} hint="at least 10 characters" />
        <button className="rounded bg-slate-900 py-1.5 text-sm text-white">Change password</button>
      </form>
    </div>
  );
}
