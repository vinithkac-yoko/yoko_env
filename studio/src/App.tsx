import { useEffect, useState } from "react";
import {
  type BuildInfo,
  type FixtureFile,
  fetchBuild,
  fetchFixtures,
  fetchHealth,
  shortSha,
} from "./api";

const TOKEN_KEY = "yoko.studio.token";

function loadToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export default function App() {
  const [health, setHealth] = useState<string>("checking…");
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [token, setToken] = useState(loadToken);
  const [files, setFiles] = useState<FixtureFile[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => setHealth(h.status))
      .catch(() => setHealth("unreachable"));
    fetchBuild().then(setBuild).catch(() => setBuild(null));
  }, []);

  const loadFixtures = () => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage can be blocked; the token still works for this session */
    }
    setError(null);
    fetchFixtures(token)
      .then(setFiles)
      .catch((e: Error) => {
        setFiles(null);
        setError(e.message);
      });
  };

  return (
    <main className="mx-auto max-w-3xl p-6 font-sans text-slate-900">
      <h1 className="text-2xl font-semibold">yoko-env studio</h1>
      <p className="text-slate-600">Phase 0: scaffold. The engine arrives in Phase 1.</p>

      <section className="mt-6 rounded border p-4">
        <h2 className="font-medium">Status</h2>
        <dl className="mt-2 grid grid-cols-[10rem_1fr] gap-y-1 text-sm">
          <dt>Health</dt>
          <dd data-testid="health">{health}</dd>
          <dt>Build</dt>
          <dd className="font-mono">{build ? shortSha(build.git_sha) : "…"}</dd>
          <dt>Seamly2D pin</dt>
          <dd className="font-mono">{build?.seamly2d_pin ?? "…"}</dd>
          <dt>Formats read</dt>
          <dd className="font-mono">{build ? build.pattern_formats_read.join(" to ") : "…"}</dd>
          <dt>Fixtures hash</dt>
          <dd className="font-mono">{build?.fixtures_hash?.slice(0, 12) ?? "…"}</dd>
        </dl>
      </section>

      <section className="mt-6 rounded border p-4">
        <h2 className="font-medium">Library: fixtures</h2>
        <div className="mt-2 flex gap-2">
          <input
            type="password"
            className="flex-1 rounded border px-2 py-1 text-sm"
            placeholder="STUDIO_TOKEN"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <button className="rounded bg-slate-900 px-3 py-1 text-sm text-white" onClick={loadFixtures}>
            Load
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
        {files && (
          <ul className="mt-3 space-y-1 text-sm">
            {files.map((f) => (
              <li key={f.path} className="flex justify-between gap-4">
                <span className="font-mono">{f.path}</span>
                <span className="text-slate-500">
                  {f.area === "base" ? "locked base" : f.area} · {f.sha256.slice(0, 8)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
