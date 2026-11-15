import { useEffect, useState } from "react";
import {
  createItem,
  type Item,
  listItems,
  listMeasurements,
  listPatterns,
  listRecipes,
  type MeasurementFile,
  patternSizes,
  type SizeChoice,
  type StartPattern,
} from "../api";
import { go } from "../router";

/** All the work items you may see, and a form to start one. */
export default function Items() {
  const [items, setItems] = useState<Item[]>([]);
  const [hidden, setHidden] = useState(0);
  const [making, setMaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    listItems()
      .then((r) => {
        setItems(r.items);
        setHidden(r.hidden);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Work items</h1>
        <button onClick={() => setMaking(true)} className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white">
          New item
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {making && <NewItemForm onCancel={() => setMaking(false)} />}
      <table className="mt-4 w-full text-sm">
        <thead className="text-left text-slate-500">
          <tr><th className="py-1">Item</th><th>What</th><th>Who</th><th>Status</th></tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={() => go(`items/${i.id}`)}>
              <td className="py-2 font-medium">{i.title}</td>
              <td>{i.kind === "recipe_example" ? `${i.recipe} · example ${i.example_no}` : "design"}</td>
              <td>{i.author}</td>
              <td>{i.status}</td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={4} className="py-4 text-slate-500">No items yet.</td></tr>
          )}
        </tbody>
      </table>
      {hidden > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          {hidden} other version{hidden === 1 ? " is" : "s are"} hidden: another maker's recipe
          example shows once you have both finished it (a blind cross-check).
        </p>
      )}
    </div>
  );
}

function NewItemForm({ onCancel }: { onCancel: () => void }) {
  const [kind, setKind] = useState<Item["kind"]>("recipe_example");
  const [recipes, setRecipes] = useState<string[]>([]);
  const [recipe, setRecipe] = useState("");
  const [example, setExample] = useState(1);
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [patterns, setPatterns] = useState<StartPattern[]>([]);
  const [start, setStart] = useState("");
  const [pieces, setPieces] = useState<string[]>([]);
  const [sizes, setSizes] = useState<SizeChoice[]>([]);
  const [size, setSize] = useState("");
  const [people, setPeople] = useState<MeasurementFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRecipes().then(setRecipes).catch(() => setRecipes([]));
    listPatterns().then((p) => {
      setPatterns(p);
      if (p.length) setStart(p[0].id);
    });
    listMeasurements().then(setPeople).catch(() => setPeople([]));
  }, []);
  useEffect(() => {
    if (!start) return;
    patternSizes(start).then((s) => {
      setSizes(s.sizes);
      setSize(s.default);
    });
  }, [start]);

  const pattern = patterns.find((p) => p.id === start);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const [k, a, b] = size.split(":");
    try {
      const { id } = await createItem({
        kind,
        recipe: kind === "recipe_example" ? recipe : null,
        example_no: kind === "recipe_example" ? example : null,
        title,
        brief,
        start_pattern: start,
        pieces,
        measurements: k === "person" ? { kind: "person", id: Number(a) } : { kind: "table", size: Number(a), height: Number(b) },
      });
      go(`items/${id}`);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <form onSubmit={submit} className="mt-4 grid gap-3 rounded border bg-slate-50 p-4 text-sm" data-testid="new-item">
      <div className="flex gap-4">
        {(["recipe_example", "design"] as const).map((k) => (
          <label key={k} className="flex items-center gap-1">
            <input type="radio" checked={kind === k} onChange={() => setKind(k)} />
            {k === "recipe_example" ? "Recipe example" : "Design"}
          </label>
        ))}
      </div>
      {kind === "recipe_example" ? (
        <div className="flex gap-3">
          <label className="flex-1">
            Recipe (pick one, or type a NEW name)
            <input list="recipes" value={recipe} onChange={(e) => setRecipe(e.target.value)} required
              pattern="[a-z][a-z0-9_]*" className="mt-1 w-full rounded border px-2 py-1.5 font-mono" />
            <datalist id="recipes">{recipes.map((r) => <option key={r} value={r} />)}</datalist>
          </label>
          <label>
            Example
            <select value={example} onChange={(e) => setExample(Number(e.target.value))}
              className="mt-1 block rounded border px-2 py-1.5">
              {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        </div>
      ) : (
        <label>
          Brief
          <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={3}
            className="mt-1 w-full rounded border px-2 py-1.5" />
          <span className="text-xs text-slate-500">Reference images come with stage E (they need the bucket).</span>
        </label>
      )}
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required
          className="mt-1 w-full rounded border px-2 py-1.5" />
      </label>
      <div className="flex gap-3">
        <label className="flex-1">
          Start from
          <select value={start} onChange={(e) => { setStart(e.target.value); setPieces([]); }}
            className="mt-1 w-full rounded border px-2 py-1.5">
            {patterns.map((p) => (
              <option key={p.id} value={p.id}>{p.name}{p.locked ? " (locked block: you get a copy)" : ""}</option>
            ))}
          </select>
        </label>
        <label className="flex-1">
          Measurements
          <select value={size} onChange={(e) => setSize(e.target.value)} className="mt-1 w-full rounded border px-2 py-1.5">
            {sizes.filter((s) => s.key.startsWith("table")).map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            {people.map((p) => <option key={p.id} value={`person:${p.id}`}>{p.name} (own measurements)</option>)}
          </select>
        </label>
      </div>
      {pattern && (
        <fieldset>
          <legend>Pieces this item is about</legend>
          <div className="mt-1 flex flex-wrap gap-3">
            {pattern.pieces.map((n) => (
              <label key={n} className="flex items-center gap-1">
                <input type="checkbox" checked={pieces.includes(n)}
                  onChange={(e) => setPieces(e.target.checked ? [...pieces, n] : pieces.filter((x) => x !== n))} />
                {n}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {error && <p className="text-red-700" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button className="rounded bg-slate-900 px-3 py-1.5 text-white">Start</button>
        <button type="button" onClick={onCancel} className="rounded border px-3 py-1.5">Cancel</button>
      </div>
    </form>
  );
}
