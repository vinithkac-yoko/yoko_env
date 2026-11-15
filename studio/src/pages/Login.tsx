import { useState } from "react";
import { type AuthStatus, login, type Person, setup } from "../api";

interface Props {
  status: AuthStatus;
  onIn: (p: Person) => void;
}

/** Sign in; or, the very first time, make the owner account with the studio token. */
export default function Login({ status, onIn }: Props) {
  const first = !status.owner_exists;
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!status.database || !status.session_secret)
    return (
      <Card title="The studio is not set up yet">
        <p className="text-sm text-slate-700">
          {!status.database && <>The database is missing: {status.database_problem || "set DATABASE_URL"}. </>}
          {!status.session_secret && <>SESSION_SECRET is not set.</>}
        </p>
        <p className="mt-2 text-sm text-slate-500">See docs/studio-v0-plan.md, Railway variables.</p>
      </Card>
    );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onIn(first ? await setup({ token, email, name, password }) : await login(email, password));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={first ? "Make the owner account" : "Sign in"}>
      {first && (
        <p className="mb-3 text-sm text-slate-600">
          This is done once. Use the studio token from Railway (STUDIO_TOKEN); afterwards you sign in
          with your email and password, and you add the pattern makers yourself.
        </p>
      )}
      <form onSubmit={submit} className="space-y-3">
        {first && <Field label="Studio token" type="password" value={token} onChange={setToken} />}
        {first && <Field label="Your name" value={name} onChange={setName} />}
        <Field label="Email" type="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" value={password} onChange={setPassword}
          hint={first ? "at least 10 characters" : undefined} />
        {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
        <button disabled={busy} className="w-full rounded bg-slate-900 py-2 text-sm text-white disabled:opacity-50">
          {first ? "Make the account" : "Sign in"}
        </button>
      </form>
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6 font-sans">
      <div className="w-full max-w-sm rounded-lg border bg-white p-6 shadow-sm">
        <h1 className="mb-4 text-lg font-semibold">{title}</h1>
        {children}
      </div>
    </main>
  );
}

export function Field(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  hint?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="text-slate-700">{props.label}</span>
      <input
        type={props.type ?? "text"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        className="mt-1 w-full rounded border px-2 py-1.5"
        required
      />
      {props.hint && <span className="text-xs text-slate-500">{props.hint}</span>}
    </label>
  );
}
