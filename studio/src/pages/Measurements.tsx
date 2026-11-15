import { useEffect, useState } from "react";
import { addMeasurements, listMeasurements, type MeasurementFile } from "../api";

/** The shared list of people's own measurement files (.smis), usable in every item. */
export default function Measurements() {
  const [files, setFiles] = useState<MeasurementFile[]>([]);
  const [name, setName] = useState("");
  const [content, setContent] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const reload = () => listMeasurements().then(setFiles).catch((e: Error) => setNote(e.message));
  useEffect(() => {
    reload();
  }, []);

  const pickFile = (f: File | undefined) => {
    if (!f) return;
    if (!name) setName(f.name.replace(/\.smis$/i, ""));
    f.text().then(setContent);
  };
  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content) return;
    try {
      const r = await addMeasurements(name, content);
      setNote(`${name}: ${r.measurements} measurements added.`);
      setName("");
      setContent(null);
      reload();
    } catch (err) {
      setNote((err as Error).message);
    }
  };

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold">Measurements</h1>
      <p className="text-sm text-slate-600">
        People's own measurement files, shared by everyone and usable in any item. The table of
        sizes comes with each block and is not listed here.
      </p>
      {note && <p className="mt-3 rounded bg-amber-50 p-2 text-sm" role="status">{note}</p>}
      <ul className="mt-4 divide-y text-sm">
        {files.map((f) => (
          <li key={f.id} className="flex justify-between py-2">
            <span>{f.name}</span>
            <span className="text-slate-500">{f.unit} · added by {f.by}</span>
          </li>
        ))}
        {files.length === 0 && <li className="py-2 text-slate-500">None yet.</li>}
      </ul>
      <form onSubmit={upload} className="mt-6 grid max-w-md gap-3 rounded border p-4">
        <h2 className="font-medium">Add a person's file (.smis)</h2>
        <input type="file" accept=".smis" onChange={(e) => pickFile(e.target.files?.[0])} className="text-sm" />
        <label className="text-sm">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required
            className="mt-1 w-full rounded border px-2 py-1.5" />
        </label>
        <button disabled={!content} className="rounded bg-slate-900 py-1.5 text-sm text-white disabled:opacity-50">
          Add
        </button>
      </form>
    </div>
  );
}
