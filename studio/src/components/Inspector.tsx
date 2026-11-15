import type { ObjectInfo, ObjectRef } from "../api";

interface Props {
  info: ObjectInfo | null;
  loading: boolean;
  onSelect: (id: number) => void;
}

/** One object: how it was made (its formulas), where it is, what it is built from and what is
 * built from it. Read-only in stage A. */
export default function Inspector({ info, loading, onSelect }: Props) {
  if (loading) return <p className="p-4 text-sm text-slate-500">Loading…</p>;
  if (!info)
    return <p className="p-4 text-sm text-slate-500">Click a point, line or curve to see how it was made.</p>;
  const refs = (list: ObjectRef[]) =>
    list.length === 0 ? (
      <span className="text-slate-400">nothing</span>
    ) : (
      <span className="flex flex-wrap gap-1">
        {list.map((r) => (
          <button key={r.id} onClick={() => onSelect(r.id)}
            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs hover:bg-slate-200">
            {r.name}
          </button>
        ))}
      </span>
    );
  return (
    <div className="space-y-3 p-4 text-sm" data-testid="inspector">
      <div>
        <h2 className="font-mono text-lg font-semibold">{info.name}</h2>
        <p className="text-slate-500">
          {info.kind}
          {info.tool && <> · drawn with <span className="font-mono">{info.tool}</span></>}
        </p>
      </div>
      {info.x_mm !== undefined && (
        <p className="font-mono text-xs text-slate-600">
          x {(info.x_mm / 10).toFixed(2)} cm · y {(info.y_mm! / 10).toFixed(2)} cm
        </p>
      )}
      {info.length !== undefined && (
        <p className="font-mono text-xs text-slate-600">length {info.length} {info.unit}</p>
      )}
      {info.attributes && (
        <table className="w-full text-xs">
          <tbody>
            {Object.entries(info.attributes).map(([k, v]) => (
              <tr key={k} className="border-b border-slate-100">
                <td className="py-1 pr-2 text-slate-500">{k}</td>
                <td className="py-1 font-mono break-all">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div>
        <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Built from</p>
        {refs(info.built_from_ids)}
      </div>
      <div>
        <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Used by</p>
        {refs(info.used_by_ids)}
      </div>
      {info.proposed_landmarks.length > 0 && (
        <div>
          <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Proposed landmark names</p>
          <p className="text-xs italic text-violet-700">
            {info.proposed_landmarks.join(", ")} (not confirmed by a pattern maker)
          </p>
        </div>
      )}
    </div>
  );
}
