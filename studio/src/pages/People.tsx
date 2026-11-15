import { useEffect, useState } from "react";
import { addPerson, listPeople, type Person, resetPassword, setDisabled } from "../api";
import { Field } from "./Login";

/** The owner's page: add pattern makers, reset a password, disable an account. */
export default function People() {
  const [people, setPeople] = useState<Person[]>([]);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const reload = () => listPeople().then(setPeople).catch((e: Error) => setNote(e.message));
  useEffect(() => {
    reload();
  }, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addPerson({ email, name, password });
      setNote(`${name} can now sign in with ${email} and the password you chose. Tell them yourself.`);
      setEmail("");
      setName("");
      setPassword("");
      reload();
    } catch (err) {
      setNote((err as Error).message);
    }
  };
  const reset = async (p: Person) => {
    const pw = window.prompt(`New password for ${p.name} (at least 10 characters)`);
    if (!pw) return;
    try {
      await resetPassword(p.id, pw);
      setNote(`${p.name}'s password is changed; they are signed out everywhere.`);
    } catch (err) {
      setNote((err as Error).message);
    }
  };
  const toggle = async (p: Person) => {
    try {
      await setDisabled(p.id, !p.disabled);
      reload();
    } catch (err) {
      setNote((err as Error).message);
    }
  };

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold">People</h1>
      <p className="text-sm text-slate-600">Only you add people. Nobody gets an email: give them their password yourself.</p>
      {note && <p className="mt-3 rounded bg-amber-50 p-2 text-sm" role="status">{note}</p>}
      <table className="mt-4 w-full text-sm">
        <thead className="text-left text-slate-500">
          <tr><th className="py-1">Name</th><th>Email</th><th>Role</th><th /></tr>
        </thead>
        <tbody>
          {people.map((p) => (
            <tr key={p.id} className={`border-t ${p.disabled ? "text-slate-400" : ""}`}>
              <td className="py-2">{p.name}</td>
              <td>{p.email}</td>
              <td>{p.role}{p.disabled && " (disabled)"}</td>
              <td className="space-x-2 text-right">
                <button className="text-slate-700 underline" onClick={() => reset(p)}>Reset password</button>
                {p.role !== "owner" && (
                  <button className="text-slate-700 underline" onClick={() => toggle(p)}>
                    {p.disabled ? "Enable" : "Disable"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={add} className="mt-6 grid max-w-md gap-3 rounded border p-4">
        <h2 className="font-medium">Add a pattern maker</h2>
        <Field label="Name" value={name} onChange={setName} />
        <Field label="Email" type="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" value={password} onChange={setPassword} hint="at least 10 characters" />
        <button className="rounded bg-slate-900 py-1.5 text-sm text-white">Add</button>
      </form>
    </div>
  );
}
